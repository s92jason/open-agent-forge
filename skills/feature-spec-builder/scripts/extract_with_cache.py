#!/usr/bin/env python3
"""Cache-aware orchestrator for Figma/Axure extraction.

Single rule: when extracting a design source, check cache first; on hit, skip
the extractor. On miss, invoke the underlying extractor (which writes both the
JSON output and its `.cache.json` sibling via `cache_helper`).

Single exception: callers running Update menu A/B pass `--bust-cache` to delete
the existing cache for the user-provided URL before checking — this turns the
hit-path into a miss-path, forcing a fresh fetch. The rationale is that
re-listing a URL in menu A/B is the user's explicit refresh intent.

Per-link files live at `<feature-dir>/<source_type>/<8-char-hash>.json`, where
hash = sha256("<source_type>|<url>|<page or empty>")[:8]. This naturally
sidesteps the previous design's single-file overwrite problem when a user
provides multiple links in one round.

Usage:
    python3 extract_with_cache.py figma "<url>" --page "<name>" \\
        --feature-dir <abs-path> [--bust-cache]
    python3 extract_with_cache.py axure "<url>" \\
        --feature-dir <abs-path> [--bust-cache]

Exit codes:
    0  cache hit, or extractor succeeded
    >0 extractor error (propagated)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional, Tuple

SCRIPT_DIR = Path(__file__).resolve().parent
EXTRACTOR_MAP = {
    "figma": "extract_figma_page.py",
    "axure": "extract_axure_page.py",
}
HASH_LENGTH = 8


def compute_link_hash(source_type: str, source_url: str, source_page: Optional[str]) -> str:
    key = "|".join([source_type, source_url, source_page or ""])
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:HASH_LENGTH]


def compute_output_path(feature_dir: Path, source_type: str, link_hash: str) -> Path:
    return feature_dir / source_type / f"{link_hash}.json"


def check_cache_hit(
    output_path: Path, source_type: str, source_url: str, source_page: Optional[str]
) -> Tuple[bool, Optional[str]]:
    """Return (hit, reason_if_miss). reason is None when no cache file exists."""
    cache_path = output_path.with_suffix(".cache.json")
    if not cache_path.exists() or not output_path.exists():
        return False, None

    try:
        meta = json.loads(cache_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return False, "cache_unreadable"

    if meta.get("source_type") != source_type:
        return False, "source_type_mismatch"
    if meta.get("source_url") != source_url:
        return False, "source_url_mismatch"
    if (meta.get("source_page") or None) != (source_page or None):
        return False, "source_page_mismatch"

    try:
        fetched_at = datetime.fromisoformat(meta["fetched_at"])
    except (KeyError, ValueError):
        return False, "fetched_at_invalid"
    ttl_days = int(meta.get("ttl_days", 7))
    if datetime.now(timezone.utc) - fetched_at > timedelta(days=ttl_days):
        return False, "ttl_expired"

    expected_sha = meta.get("output_sha256")
    actual_sha = hashlib.sha256(output_path.read_bytes()).hexdigest()
    if expected_sha != actual_sha:
        return False, "integrity_failed"

    return True, None


def bust_cache(output_path: Path) -> list[Path]:
    cache_path = output_path.with_suffix(".cache.json")
    removed = []
    for p in (output_path, cache_path):
        if p.exists():
            p.unlink()
            removed.append(p)
    return removed


def run_extractor(
    source_type: str, source_url: str, source_page: Optional[str], output_path: Path
) -> int:
    extractor_script = SCRIPT_DIR / EXTRACTOR_MAP[source_type]
    output_path.parent.mkdir(parents=True, exist_ok=True)

    cmd = [sys.executable, str(extractor_script), source_url, "--output", str(output_path)]
    if source_type == "figma" and source_page:
        cmd += ["--page", source_page]

    return subprocess.run(cmd, check=False).returncode


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Cache-aware wrapper for Figma/Axure extractors."
    )
    parser.add_argument("source_type", choices=list(EXTRACTOR_MAP.keys()))
    parser.add_argument("url", help="Source URL (Figma file/page/frame, or Axure share link)")
    parser.add_argument("--page", default=None, help="Figma page name (ignored for Axure)")
    parser.add_argument(
        "--feature-dir",
        required=True,
        help="Feature artifact root, e.g. <repo>/.ai-artifacts/feature-spec-builder/<feature>",
    )
    parser.add_argument(
        "--bust-cache",
        action="store_true",
        help="Delete existing cache before checking. Use when caller treats the URL as an explicit refresh request (Update menu A/B).",
    )
    args = parser.parse_args()

    feature_dir = Path(args.feature_dir).resolve()
    link_hash = compute_link_hash(args.source_type, args.url, args.page)
    output_path = compute_output_path(feature_dir, args.source_type, link_hash)

    if args.bust_cache:
        removed = bust_cache(output_path)
        if removed:
            print(f"CACHE_BUSTED: removed {len(removed)} file(s) for {args.url}", file=sys.stderr)

    hit, reason = check_cache_hit(output_path, args.source_type, args.url, args.page)
    if hit:
        print(f"CACHE_HIT: {output_path}")
        return 0
    if reason:
        print(f"CACHE_MISS ({reason}): re-extracting", file=sys.stderr)

    rc = run_extractor(args.source_type, args.url, args.page, output_path)
    if rc == 0:
        print(f"EXTRACTED: {output_path}")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
