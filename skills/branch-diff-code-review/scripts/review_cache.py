#!/usr/bin/env python3
"""Review cache helper for the branch-diff-code-review skill.

Subcommands:
  check    Print HIT/MISS based on (base_commit, head_commit, rules_hash,
           schema_version) match. Stdout = JSON.
  finalize After the skill has written `review-output.md` via the Write tool,
           compute its sha256 and persist `cache.json` so the next same-HEAD
           invocation can detect HIT.

Cache fingerprint is content-addressed over the rule files that shape the
review (SKILL.md + scoring-rubric.md + review-checklist.md + chunking.md +
business-logic-heuristics.md). Any rule edit invalidates conservatively.

By design there is no dialogue-level "force refresh" command. Users bust the
cache with `rm -rf <repo>/.ai-artifacts/branch-diff-code-review/` — the same
action that resets the bundle. This follows the project Cache 化原則
(see top-level CLAUDE.md): 明示意圖 = 動作而非指令。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
SCHEMA_VERSION = 1

RULE_FILES = [
    SKILL_DIR / "SKILL.md",
    SKILL_DIR / "references" / "scoring-rubric.md",
    SKILL_DIR / "references" / "review-checklist.md",
    SKILL_DIR / "references" / "chunking.md",
    SKILL_DIR / "references" / "business-logic-heuristics.md",
]


def resolve_bundle_dir() -> Path:
    return Path(os.environ.get("BUNDLE_DIR", ".ai-artifacts/branch-diff-code-review"))


def compute_rules_hash() -> str:
    """Sha256 over rule files. Missing files are skipped silently (forward-compat)."""
    h = hashlib.sha256()
    for f in RULE_FILES:
        if f.exists():
            h.update(f.name.encode("utf-8"))
            h.update(b"\n")
            h.update(f.read_bytes())
            h.update(b"\n---\n")
    return h.hexdigest()


def read_json_file(path: Path) -> Optional[dict]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None


def cmd_check() -> int:
    bundle = resolve_bundle_dir()
    manifest_path = bundle / "manifest.json"
    cache_path = bundle / "cache.json"
    review_path = bundle / "review-output.md"

    result = {
        "hit": False,
        "reason": None,
        "review_output_path": str(review_path),
    }

    manifest = read_json_file(manifest_path)
    if not manifest:
        result["reason"] = "manifest_missing"
        print(json.dumps(result, ensure_ascii=False))
        return 0

    cache = read_json_file(cache_path)
    if not cache:
        result["reason"] = "cache_missing"
        print(json.dumps(result, ensure_ascii=False))
        return 0

    if not review_path.exists():
        result["reason"] = "review_output_missing"
        print(json.dumps(result, ensure_ascii=False))
        return 0

    if cache.get("schema_version") != SCHEMA_VERSION:
        result["reason"] = "schema_version_mismatch"
        print(json.dumps(result, ensure_ascii=False))
        return 0

    if cache.get("base_commit") != manifest.get("base_commit"):
        result["reason"] = "base_commit_mismatch"
        print(json.dumps(result, ensure_ascii=False))
        return 0

    if cache.get("head_commit") != manifest.get("head"):
        result["reason"] = "head_commit_mismatch"
        print(json.dumps(result, ensure_ascii=False))
        return 0

    if cache.get("rules_hash") != compute_rules_hash():
        result["reason"] = "rules_hash_mismatch"
        print(json.dumps(result, ensure_ascii=False))
        return 0

    actual_sha = hashlib.sha256(review_path.read_bytes()).hexdigest()
    if cache.get("review_output_sha256") != actual_sha:
        result["reason"] = "review_output_integrity_failed"
        print(json.dumps(result, ensure_ascii=False))
        return 0

    result["hit"] = True
    result["saved_at"] = cache.get("saved_at")
    result["base_commit"] = cache.get("base_commit")
    result["head_commit"] = cache.get("head_commit")
    print(json.dumps(result, ensure_ascii=False))
    return 0


def cmd_finalize() -> int:
    bundle = resolve_bundle_dir()
    manifest_path = bundle / "manifest.json"
    review_path = bundle / "review-output.md"

    manifest = read_json_file(manifest_path)
    if not manifest:
        print(f"ERROR: manifest not found at {manifest_path}", file=sys.stderr)
        return 1
    if not review_path.exists():
        print(
            "ERROR: review-output.md not found at "
            f"{review_path}. Write the final review to that path first "
            "(use the Write tool), then re-run finalize.",
            file=sys.stderr,
        )
        return 1

    cache = {
        "schema_version": SCHEMA_VERSION,
        "rules_hash": compute_rules_hash(),
        "base_commit": manifest.get("base_commit"),
        "head_commit": manifest.get("head"),
        "review_output_sha256": hashlib.sha256(review_path.read_bytes()).hexdigest(),
        "saved_at": datetime.now(timezone.utc).isoformat(),
    }
    cache_path = bundle / "cache.json"
    cache_path.write_text(
        json.dumps(cache, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps({"ok": True, "cache_path": str(cache_path)}, ensure_ascii=False))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="branch-diff-code-review cache helper (check / finalize)."
    )
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser(
        "check",
        help="Check if cached review is reusable for the current HEAD/base. "
             "Stdout = JSON with `hit` and `reason`.",
    )
    sub.add_parser(
        "finalize",
        help="Persist review-output.md as cache after the skill finishes the review.",
    )
    args = parser.parse_args()

    if args.cmd == "check":
        return cmd_check()
    if args.cmd == "finalize":
        return cmd_finalize()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
