"""
build_commit_bundle.py
======================
收集當前 Git 倉庫的 commit 相關資訊，產生結構化的 bundle 檔案。

輸出檔案：
  - .ai-artifacts/smart-commit-flow/commit_bundle.md   (人類可讀的 Markdown 格式)
  - .ai-artifacts/smart-commit-flow/commit_bundle.json (機器可讀的 JSON 格式)

用途：
  供 smart-commit-flow skill 分析 staged diff，產生合適的 commit message。

環境變數：
  OUT_DIR — 覆寫輸出目錄（預設：.ai-artifacts/smart-commit-flow）
"""
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

from git_helpers import must_git, run, safe_strip, try_run

# 輸出目錄與檔案路徑（可由 OUT_DIR 環境變數覆寫）
OUT_DIR = Path(os.environ.get("OUT_DIR", ".ai-artifacts/smart-commit-flow"))
MD_PATH = OUT_DIR / "commit_bundle.md"
JSON_PATH = OUT_DIR / "commit_bundle.json"


def main() -> None:
    """主程式進入點：收集 git 資訊並輸出 bundle 檔案。"""
    # 確認當前目錄是 git 倉庫，否則拋出錯誤
    must_git()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # 記錄產生時間（ISO 格式，精確到秒）
    now = datetime.now().isoformat(timespec="seconds")

    # 取得基本倉庫資訊
    repo_root = safe_strip(run(["git", "rev-parse", "--show-toplevel"]).stdout)
    branch = safe_strip(run(["git", "branch", "--show-current"]).stdout)
    head_sha = safe_strip(run(["git", "rev-parse", "HEAD"]).stdout)

    # 取得 git status（porcelain 格式，方便程式解析）
    status = run(["git", "status", "--porcelain=v1"]).stdout

    # 取得 git 使用者身份（可能未設定）
    user_name = try_run(["git", "config", "user.name"])
    user_email = try_run(["git", "config", "user.email"])

    # 取得 staged（已暫存）與 unstaged（未暫存）的變更清單
    staged_name_status = run(["git", "diff", "--cached", "--name-status"]).stdout
    unstaged_name_status = run(["git", "diff", "--name-status"]).stdout

    # 取得 staged 變更的統計資訊與完整 diff
    staged_numstat = run(["git", "diff", "--cached", "--numstat"]).stdout  # 增刪行數
    staged_stat = run(["git", "diff", "--cached", "--stat"]).stdout        # 簡易統計
    staged_diff = run(["git", "diff", "--cached"]).stdout                  # 完整 diff

    # 取得 remote 與 upstream 資訊
    remotes = run(["git", "remote", "-v"]).stdout
    upstream_r = run(["git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"])
    upstream = safe_strip(upstream_r.stdout) if upstream_r.code == 0 else ""

    # 計算與 upstream 的 ahead/behind 數量
    ahead_behind = ""
    if upstream:
        # 輸出格式："<behind>\t<ahead>"，例如 "3\t1" 表示落後 3 個、領先 1 個
        counts = try_run(["git", "rev-list", "--left-right", "--count", f"{upstream}...HEAD"])
        ahead_behind = counts

    # 組裝 JSON payload
    payload = {
        "generated_at": now,
        "repo_root": repo_root,
        "branch": branch,
        "head_sha": head_sha,
        "identity": {
            "user.name": user_name,
            "user.email": user_email,
        },
        "git_status_porcelain": status,
        "staged_name_status": staged_name_status,
        "unstaged_name_status": unstaged_name_status,
        "staged_numstat": staged_numstat,
        "staged_stat": staged_stat,
        "staged_diff": staged_diff,
        "remotes": remotes,
        "upstream": upstream,
        "upstream_ahead_behind": ahead_behind,  # behind\tahead (if upstream exists)
    }

    # 寫入 JSON 檔案
    JSON_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    # 產生 Markdown 格式的 bundle（供人類閱讀）
    md = []

    # 標題與產生時間
    md.append(f"# Commit Bundle\n\nGenerated at: `{now}`\n")

    # 倉庫與 HEAD 資訊
    md.append("\n## Repo / HEAD\n")
    md.append(f"- Repo root: `{repo_root}`\n")
    md.append(f"- Branch: `{branch or '(detached/unknown)'}`\n")
    md.append(f"- HEAD: `{head_sha}`\n")

    # 使用者身份
    md.append("\n## Identity (git config)\n")
    md.append(f"- user.name: `{user_name or '(unset)'}`\n")
    md.append(f"- user.email: `{user_email or '(unset)'}`\n")

    # Upstream 追蹤資訊
    md.append("\n## Upstream\n")
    md.append(f"- Upstream: `{upstream or '(none)'}`\n")
    if upstream and ahead_behind:
        md.append(f"- Behind/Ahead: `{ahead_behind}` (format: behind\\tahead)\n")

    # 各項 git 資訊區塊
    md.append("\n## Remotes\n```text\n" + (remotes or "").rstrip() + "\n```\n")
    md.append("\n## Status (porcelain)\n```text\n" + (status or "").rstrip() + "\n```\n")
    md.append("\n## Staged changes (name-status)\n```text\n" + (staged_name_status or "").rstrip() + "\n```\n")
    md.append("\n## Unstaged changes (name-status)\n```text\n" + (unstaged_name_status or "").rstrip() + "\n```\n")
    md.append("\n## Staged changes (stat)\n```text\n" + (staged_stat or "").rstrip() + "\n```\n")
    md.append("\n## Staged changes (numstat)\n```text\n" + (staged_numstat or "").rstrip() + "\n```\n")

    # 完整的 staged diff（最重要的部分，用於產生 commit message）
    md.append("\n## Staged diff\n```diff\n" + (staged_diff or "").rstrip() + "\n```\n")

    # 寫入 Markdown 檔案
    MD_PATH.write_text("".join(md), encoding="utf-8")

    print(f"[ok] wrote {MD_PATH}")
    print(f"[ok] wrote {JSON_PATH}")


if __name__ == "__main__":
    main()
