#!/usr/bin/env python3
"""Build a review bundle from the current branch diff.

Outputs:
  .ai-artifacts/branch-diff-code-review/
    manifest.json          — range, base, head, file stats, chunk list
    chunks/chunk-01.md     — per-chunk review content
    all-in-one.md          — merged content (only when under token limit)

Environment overrides:
  MAX_TOKENS   — token budget per chunk (default: 12000)
  BUNDLE_DIR   — output directory (default: .ai-artifacts/branch-diff-code-review)
  BASE_REF     — local branch/tag to use as base
  BASE_COMMIT  — exact SHA to use as base
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional

SKILL_DIR = Path(__file__).resolve().parent.parent


def _shared_scripts_dir() -> Path:
    """找出 shared/scripts：plugin 佈局在 skill 的上兩層，攤平（或匯出安裝）的佈局在上一層。

    不能用固定層數：同一個檔會出現在兩種佈局裡（公開庫的 plugins/ 與 skills/ 內容相同），
    兩個位置都找，搬的時候才不用改寫路徑。和 pr-review 的 pr_review.py 同一個做法。
    """
    for candidate in (
        SKILL_DIR.parent.parent / "shared" / "scripts",
        SKILL_DIR.parent / "shared" / "scripts",
    ):
        if (candidate / "utils.py").exists():
            return candidate
    raise SystemExit(
        "找不到 shared/scripts/utils.py；branch-diff-code-review 必須與 forge-git-flow 的共用腳本一起安裝"
        "（單獨複製這個 skill 時，把 shared/ 放在它的旁邊）。"
    )


SHARED_SCRIPTS = _shared_scripts_dir()
sys.path.insert(0, str(SHARED_SCRIPTS))

from utils import (
    resolve_branch_base,
    list_changed_files,
    unified_diff,
    file_text_at,
    is_probably_binary,
    is_excluded_path,
    approx_tokens,
    group_key_for_path,
    package_prefix,
    detect_sensitive_markers,
    write_text,
    write_json,
    safe_mkdir,
)

MAX_TOKENS = int(os.environ.get("MAX_TOKENS", "12000"))
BUNDLE_DIR = Path(os.environ.get("BUNDLE_DIR", ".ai-artifacts/branch-diff-code-review"))

# Paths containing these substrings are always isolated into their own chunk.
_FORCE_ISOLATE = [
    "migration", "schema",
    "auth", "security", "crypto", "keystore",
    "payment", "transaction", "checkout",
    "analytics", "tracking",
]


def _force_isolate_key(path: str) -> Optional[str]:
    lp = path.lower()
    for pattern in _FORCE_ISOLATE:
        if pattern in lp:
            return f"isolated-{pattern}"
    return None


def _build_entry(base: str, head: str, f: Dict) -> Optional[Dict]:
    path = f["path"]
    status = f["status"]

    if is_excluded_path(path):
        return None

    diff = unified_diff(base, head, path)
    if not diff or is_probably_binary(diff):
        return None

    base_text = file_text_at(base, path) if status != "A" else None
    head_text = file_text_at(head, path) if status != "D" else None

    pkg = None
    for text in (head_text, base_text):
        if text and not is_probably_binary(text):
            pkg = package_prefix(text)
            if pkg:
                break

    return {
        "path": path,
        "old_path": f.get("old_path"),
        "status": status,
        "diff": diff,
        "base_text": base_text,
        "head_text": head_text,
        "package": pkg,
        "token_estimate": approx_tokens(diff),
        "sensitive_markers": detect_sensitive_markers(diff),
    }


def _group(entries: List[Dict]) -> Dict[str, List[Dict]]:
    groups: Dict[str, List[Dict]] = {}
    for entry in entries:
        key = _force_isolate_key(entry["path"]) or group_key_for_path(entry["path"])
        groups.setdefault(key, []).append(entry)
    return groups


def _split_chunks(groups: Dict[str, List[Dict]], max_tokens: int) -> List[List[Dict]]:
    chunks: List[List[Dict]] = []
    current: List[Dict] = []
    current_tokens = 0

    for entries in groups.values():
        group_tokens = sum(e["token_estimate"] for e in entries)
        if current and current_tokens + group_tokens > max_tokens:
            chunks.append(current)
            current = []
            current_tokens = 0
        current.extend(entries)
        current_tokens += group_tokens

    if current:
        chunks.append(current)
    return chunks


_STATUS_LABEL = {"A": "Added", "D": "Deleted", "M": "Modified", "R": "Renamed"}


def _render_file(entry: Dict) -> str:
    label = _STATUS_LABEL.get(entry["status"], entry["status"])
    old = entry.get("old_path")
    heading = (
        f"## `{old}` → `{entry['path']}` [{label}]"
        if old
        else f"## `{entry['path']}` [{label}]"
    )

    parts = [heading]

    if entry["sensitive_markers"]:
        markers = ", ".join(entry["sensitive_markers"])
        parts.append(f"\n> ⚠️ **Sensitive markers detected**: {markers}\n")

    parts.append(f"\n```diff\n{entry['diff']}\n```")
    return "\n".join(parts)


def _render_chunk(entries: List[Dict], num: int, total: int, info: Dict) -> str:
    base_short = (info.get("base_commit") or "")[:8]
    head_short = (info.get("head") or "")[:8]
    header = "\n".join([
        f"# Code Review Bundle — Chunk {num}/{total}",
        "",
        f"**Range**: `{info.get('range', 'unknown')}`",
        f"**Base**: `{info.get('base_ref', 'N/A')}` @ `{base_short}`",
        f"**Head**: `{head_short}`",
        f"**Files in this chunk**: {len(entries)}",
        "",
    ])
    sections = "\n\n".join(_render_file(e) for e in entries)
    return header + sections + "\n"


def main() -> None:
    info = resolve_branch_base()
    base = info.get("base_commit")
    head = info.get("head")

    if not base or not head:
        print(json.dumps({**info, "error": "Could not determine base commit."}, ensure_ascii=False, indent=2))
        sys.exit(1)

    changed = list_changed_files(base, head)
    entries: List[Dict] = []
    skipped: List[str] = []

    for f in changed:
        entry = _build_entry(base, head, f)
        if entry:
            entries.append(entry)
        else:
            skipped.append(f["path"])

    total_tokens = sum(e["token_estimate"] for e in entries)
    groups = _group(entries)
    chunk_lists = _split_chunks(groups, MAX_TOKENS)

    safe_mkdir(BUNDLE_DIR / "chunks")

    chunk_paths: List[str] = []
    for i, chunk_entries in enumerate(chunk_lists, 1):
        md = _render_chunk(chunk_entries, i, len(chunk_lists), info)
        path = BUNDLE_DIR / "chunks" / f"chunk-{i:02d}.md"
        write_text(path, md)
        chunk_paths.append(str(path))

    all_in_one_path = None
    if total_tokens <= MAX_TOKENS:
        md = _render_chunk(entries, 1, 1, info)
        p = BUNDLE_DIR / "all-in-one.md"
        write_text(p, md)
        all_in_one_path = str(p)

    manifest = {
        "range": info.get("range"),
        "base_ref": info.get("base_ref"),
        "base_commit": info.get("base_commit"),
        "head": info.get("head"),
        "current_branch": info.get("current_branch"),
        "total_files_changed": len(changed),
        "files_included": len(entries),
        "files_skipped": skipped,
        "total_token_estimate": total_tokens,
        "max_tokens_per_chunk": MAX_TOKENS,
        "chunks": len(chunk_lists),
        "chunk_paths": chunk_paths,
        "all_in_one": all_in_one_path,
        "notes": info.get("notes", []),
    }

    write_json(BUNDLE_DIR / "manifest.json", manifest)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
