#!/usr/bin/env python3
"""把單一檔案的 unified diff 解析成帶行號的結構。

review 頁面與 AI 都靠這份結構定位：每一行都有明確的舊行號、新行號，
意見的行號能不能對上 diff，也是用這裡的結果檢查。
"""
from __future__ import annotations

import hashlib
import re
from typing import Any, Dict, List, Optional, Set

_HUNK_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(.*)$")

DEFAULT_MAX_LINES = 4000


def parse_unified_diff(diff_text: str, max_lines: int = DEFAULT_MAX_LINES) -> Dict[str, Any]:
    """解析一個檔案的 unified diff。

    回傳的 ``hunks`` 每一行是 ``{"t": "ctx"|"add"|"del", "old": int|None, "new": int|None, "text": str}``。
    超過 ``max_lines`` 的部分不保留內容（``truncated`` 為 True），但 ``additions``、``deletions``
    與 ``signature`` 仍以完整 diff 計算。

    ``signature`` 只取增刪行的內容，不含行號與上下文，所以作者 rebase 造成行號位移時不會變。
    """
    hunks: List[Dict[str, Any]] = []
    additions = 0
    deletions = 0
    binary = False
    truncated = False
    stored = 0
    signature = hashlib.sha1()

    current: Optional[Dict[str, Any]] = None
    old_no = 0
    new_no = 0
    old_left = 0
    new_left = 0

    def keep(line: Dict[str, Any]) -> None:
        nonlocal stored, truncated
        if stored < max_lines:
            assert current is not None
            current["lines"].append(line)
            stored += 1
        else:
            truncated = True

    for raw in diff_text.split("\n"):
        header = _HUNK_RE.match(raw)
        if header:
            old_no = int(header.group(1))
            new_no = int(header.group(3))
            old_left = int(header.group(2)) if header.group(2) is not None else 1
            new_left = int(header.group(4)) if header.group(4) is not None else 1
            current = {
                "old_start": old_no,
                "new_start": new_no,
                "context": header.group(5).strip(),
                "lines": [],
            }
            hunks.append(current)
            continue

        if current is None:
            if raw.startswith("Binary files ") or raw.startswith("GIT binary patch"):
                binary = True
            continue

        if raw.startswith("\\"):
            continue
        if old_left <= 0 and new_left <= 0:
            current = None
            continue

        marker, body = raw[:1], raw[1:]
        # 簽章用原始內容（含 CRLF 的 \r），顯示用的文字去掉行尾的 \r
        text = body[:-1] if body.endswith("\r") else body
        if marker == "+":
            additions += 1
            new_left -= 1
            signature.update(b"+" + body.encode("utf-8", "replace") + b"\n")
            keep({"t": "add", "old": None, "new": new_no, "text": text})
            new_no += 1
        elif marker == "-":
            deletions += 1
            old_left -= 1
            signature.update(b"-" + body.encode("utf-8", "replace") + b"\n")
            keep({"t": "del", "old": old_no, "new": None, "text": text})
            old_no += 1
        else:
            # 空字串是「只有一個空白的上下文行」被去尾後的樣子，一樣算上下文
            old_left -= 1
            new_left -= 1
            keep({"t": "ctx", "old": old_no, "new": new_no, "text": text})
            old_no += 1
            new_no += 1

    return {
        "hunks": hunks,
        "additions": additions,
        "deletions": deletions,
        "binary": binary,
        "truncated": truncated,
        "signature": signature.hexdigest(),
    }


def diff_line_numbers(hunks: List[Dict[str, Any]], side: str) -> Set[int]:
    """回傳 diff 內某一側出現過的行號（``side`` 為 ``"new"`` 或 ``"old"``）。"""
    key = "new" if side == "new" else "old"
    numbers: Set[int] = set()
    for hunk in hunks:
        for line in hunk["lines"]:
            value = line.get(key)
            if value is not None:
                numbers.add(value)
    return numbers


def render_numbered_diff(hunks: List[Dict[str, Any]]) -> str:
    """把 hunks 排成每行都帶「舊<行號> 新<行號> 符號」的文字，給 AI 讀。

    行號前面加上「舊」「新」是為了讓每個數字自己說明身分：用 Read 讀檔時最左邊會多一欄
    Read 自己的行號，沒有標籤的話三個數字並排，很容易把它誤認成 diff 的行號。
    """
    sign = {"ctx": " ", "add": "+", "del": "-"}
    out: List[str] = []
    for hunk in hunks:
        context = f" {hunk['context']}" if hunk.get("context") else ""
        out.append(f"@@ 舊 {hunk['old_start']} / 新 {hunk['new_start']} @@{context}")
        for line in hunk["lines"]:
            old = "" if line["old"] is None else f"舊{line['old']}"
            new = "" if line["new"] is None else f"新{line['new']}"
            out.append(f"{old:>7} {new:>7} {sign[line['t']]} {line['text']}")
    return "\n".join(out)
