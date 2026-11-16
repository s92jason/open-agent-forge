#!/usr/bin/env python3
"""產生 task-brief 交接包裡的「啟動指令」與「deep link」。

輸入 kickoff prompt 文字與 model / effort / permission mode / cwd，輸出 JSON：

  {
    "command": "claude --model opus --effort high --permission-mode plan '...'",
    "deep_link": "claude-cli://open?q=...&cwd=...",   # 超過上限時為 null
    "deep_link_omitted_reason": null,                  # deep_link 為 null 時說明原因
    "prompt_length": 1234,
    "cwd": "/abs/path",
    "cwd_exists": true                                 # 目錄尚未建立時為 false
  }

設計重點：
  - command 一律是「一行」：prompt 含換行或控制字元時改用 ANSI-C quoting（$'...'），
    bash 與 zsh 都能正確還原；其餘情況用 POSIX 單引號 quoting，避免 $、`、! 被展開。
  - deep link 的 q 與 cwd 都做完整 percent-encoding（safe=""），換行、&、# 不會截斷 URL。
  - q 上限以「prompt 原文字元數」計算（DEEP_LINK_PROMPT_LIMIT），超過時只給指令。
  - cwd 可以指向尚未建立的目錄（從零建立的新專案）：指令照給、cwd_exists 為 false，
    deep link 回 null——官方文件說 cwd 不存在時 deep link 仍以它為準，開不到正確位置。
  - cwd 含控制字元或雙向控制字元時，官方 deep link 會拒絕，同樣回 null 並附原因。

全程唯讀：不寫檔、不執行 claude。

用法：
  python3 build_launch_command.py --model opus --effort high --mode plan \\
      --cwd /path/to/repo --prompt-file /path/to/prompt.md
  printf '%s' "$PROMPT" | python3 build_launch_command.py --model sonnet \\
      --effort medium --mode default --prompt -
"""

from __future__ import annotations

import argparse
import json
import shlex
import sys
from pathlib import Path
from urllib.parse import quote

MODELS: tuple[str, ...] = ("fable", "opus", "sonnet", "haiku")
EFFORTS: tuple[str, ...] = ("low", "medium", "high", "xhigh", "max")
PERMISSION_MODES: tuple[str, ...] = ("plan", "default", "acceptEdits", "auto")

DEEP_LINK_SCHEME = "claude-cli://open"
DEEP_LINK_PROMPT_LIMIT = 5000

# 官方 deep link 拒絕含不可見或雙向控制字元的 cwd。
_BIDI_CONTROLS = frozenset("\u200e\u200f\u202a\u202b\u202c\u202d\u202e\u2066\u2067\u2068\u2069")

# ANSI-C quoting 需要跳脫的字元（其餘可列印字元原樣保留，含中文）。
_ANSI_C_ESCAPES: dict[str, str] = {
    "\\": "\\\\",
    "'": "\\'",
    "\n": "\\n",
    "\r": "\\r",
    "\t": "\\t",
    # 互動式 shell 的 history expansion 是否作用於 $'...' 因 shell 而異，一律轉成 \x21。
    "!": "\\x21",
}


def _needs_ansi_c(text: str) -> bool:
    """判斷字串是否含換行或其他控制字元，需要 $'...' 才能維持單行。"""
    return any(ch in "\n\r\t" or ord(ch) < 0x20 or ord(ch) == 0x7F for ch in text)


def _ansi_c_quote(text: str) -> str:
    """以 bash / zsh 的 ANSI-C quoting（$'...'）包住字串，換行轉成 \\n。"""
    parts: list[str] = []
    for ch in text:
        if ch in _ANSI_C_ESCAPES:
            parts.append(_ANSI_C_ESCAPES[ch])
        elif ord(ch) < 0x20 or ord(ch) == 0x7F:
            parts.append(f"\\x{ord(ch):02x}")
        else:
            parts.append(ch)
    return "$'" + "".join(parts) + "'"


def shell_quote_prompt(prompt: str) -> str:
    """把 prompt 轉成可放進單行 shell 指令的引數。

    Args:
        prompt: kickoff prompt 原文，可含引號、換行、$、反引號。

    Returns:
        已跳脫的 shell 字串；含控制字元時為 $'...'，否則為 POSIX 單引號形式。
    """
    if _needs_ansi_c(prompt):
        return _ansi_c_quote(prompt)
    return shlex.quote(prompt)


def build_command(prompt: str, model: str, effort: str, mode: str) -> str:
    """組出完整的 claude 啟動指令（單行）。"""
    return (
        f"claude --model {model} --effort {effort} "
        f"--permission-mode {mode} {shell_quote_prompt(prompt)}"
    )


def _has_rejected_path_chars(path: str) -> bool:
    """判斷路徑是否含官方 deep link 會拒絕的控制字元或雙向控制字元。"""
    return any(ord(ch) < 0x20 or ord(ch) == 0x7F or ch in _BIDI_CONTROLS for ch in path)


def build_deep_link(
    prompt: str, cwd: Path, cwd_exists: bool = True
) -> tuple[str | None, str | None]:
    """組出 claude-cli:// deep link。

    Args:
        prompt: kickoff prompt 原文。
        cwd: 新 session 的工作目錄（絕對路徑）。
        cwd_exists: cwd 目前是否已存在。

    Returns:
        (deep_link, omitted_reason)。不能產生 deep link 時（cwd 尚未建立、cwd 含
        被拒絕的字元、prompt 超過上限）deep_link 為 None，omitted_reason 說明原因；
        否則 omitted_reason 為 None。
    """
    if not cwd_exists:
        reason = (
            f"目錄 {cwd} 尚未建立，deep link 無法開到正確位置；"
            "請先建立目錄，再到該目錄執行啟動指令"
        )
        return None, reason
    if _has_rejected_path_chars(str(cwd)):
        return None, "cwd 含控制字元或雙向控制字元，deep link 會被拒絕；請改用啟動指令"
    length = len(prompt)
    if length > DEEP_LINK_PROMPT_LIMIT:
        reason = (
            f"prompt 共 {length} 字，超過 deep link 的 q 參數上限 "
            f"{DEEP_LINK_PROMPT_LIMIT} 字；請改用啟動指令"
        )
        return None, reason
    link = f"{DEEP_LINK_SCHEME}?q={quote(prompt, safe='')}&cwd={quote(str(cwd), safe='')}"
    return link, None


def build_bundle(
    prompt: str, model: str, effort: str, mode: str, cwd: Path, cwd_exists: bool = True
) -> dict[str, object]:
    """產生完整輸出結構（供 CLI 與測試共用）。"""
    deep_link, reason = build_deep_link(prompt, cwd, cwd_exists)
    return {
        "command": build_command(prompt, model, effort, mode),
        "deep_link": deep_link,
        "deep_link_omitted_reason": reason,
        "prompt_length": len(prompt),
        "cwd": str(cwd),
        "cwd_exists": cwd_exists,
    }


def _read_prompt(args: argparse.Namespace) -> str:
    """依參數取得 prompt：--prompt-file、--prompt -（stdin）或 --prompt 文字。"""
    if args.prompt_file is not None:
        return Path(args.prompt_file).read_text(encoding="utf-8")
    if args.prompt == "-":
        return sys.stdin.read()
    return args.prompt


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="產生 task-brief 的 claude 啟動指令與 deep link（輸出 JSON）。",
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--prompt", help="prompt 文字；傳 - 代表從 stdin 讀取")
    source.add_argument("--prompt-file", help="從 UTF-8 檔案讀取 prompt")
    parser.add_argument("--model", required=True, choices=MODELS, help="model 別名")
    parser.add_argument("--effort", required=True, choices=EFFORTS, help="effort 等級")
    parser.add_argument("--mode", required=True, choices=PERMISSION_MODES, help="permission mode")
    parser.add_argument(
        "--cwd",
        default=".",
        help="新 session 的工作目錄（預設：目前目錄）；可指向尚未建立的目錄",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI 進入點。成功回 0；輸入錯誤回 2。"""
    args = _parse_args(argv)
    try:
        prompt = _read_prompt(args)
    except OSError as exc:
        print(f"讀取 prompt 失敗：{exc}", file=sys.stderr)
        return 2
    # 只去掉 heredoc / echo 常帶的結尾換行，內文換行保留。
    prompt = prompt.rstrip("\n")
    if not prompt.strip():
        print("prompt 是空的", file=sys.stderr)
        return 2

    cwd = Path(args.cwd).expanduser().resolve()
    if cwd.exists() and not cwd.is_dir():
        print(f"cwd 已存在但不是目錄：{cwd}", file=sys.stderr)
        return 2

    bundle = build_bundle(prompt, args.model, args.effort, args.mode, cwd, cwd.is_dir())
    json.dump(bundle, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
