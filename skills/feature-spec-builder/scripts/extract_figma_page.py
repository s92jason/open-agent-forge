#!/usr/bin/env python3
"""
Extract all top-level frames from a Figma page for engineering feature spec building.

Outputs a spec-oriented JSON with frame list, text content summaries,
and inferred UI states (loading/success/empty/error).

Usage:
    python3 extract_figma_page.py "<FIGMA_URL>" --page "Page Name"
    python3 extract_figma_page.py "<FIGMA_URL_WITH_NODE_ID>" --output path/to/figma_page.json

Default output: .ai-artifacts/feature-spec-builder/figma_page.json (relative to repo root)
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from cache_helper import write_cache_metadata

EXTRACTOR_VERSION = "1.0"


class FigmaAPIError(Exception):
    """Raised when Figma API returns an error."""

    def __init__(self, code: int, body: str) -> None:
        self.code = code
        self.body = body
        super().__init__(f"Figma API error {code}: {body}")


# ---------------------------------------------------------------------------
# Repo root detection
# ---------------------------------------------------------------------------

def _find_repo_root() -> Path:
    """Walk up from CWD to find the git repo root. Falls back to CWD."""
    current = Path.cwd()
    for parent in [current, *current.parents]:
        if (parent / ".git").exists():
            return parent
    return current


# ---------------------------------------------------------------------------
# Token resolution (priority: --token arg > env var > macOS Keychain)
# ---------------------------------------------------------------------------

_SCRIPT_DIR = Path(__file__).resolve().parent
_KEYCHAIN_HELPER = _SCRIPT_DIR / "keychain_helper.py"


def _read_token_from_keychain() -> Optional[str]:
    """Read Figma token from macOS Keychain via keychain_helper.py get."""
    try:
        result = subprocess.run(
            [sys.executable, str(_KEYCHAIN_HELPER), "get"],
            capture_output=True, text=True, check=False,
        )
        if result.returncode == 0:
            return result.stdout.strip() or None
    except FileNotFoundError:
        pass
    return None


def resolve_token(cli_token: Optional[str]) -> Optional[str]:
    """Resolve Figma token: --token arg > FIGMA_ACCESS_TOKEN env > Keychain."""
    if cli_token:
        return cli_token
    env_token = os.environ.get("FIGMA_ACCESS_TOKEN")
    if env_token:
        return env_token
    return _read_token_from_keychain()


# ---------------------------------------------------------------------------
# URL parsing (reused pattern from figma-extractor)
# ---------------------------------------------------------------------------

def parse_figma_url(url: str) -> Tuple[Optional[str], Optional[str]]:
    """Extract file_key and optional node_id from a Figma URL."""
    file_key_match = re.search(r"figma\.com/(?:file|design)/([a-zA-Z0-9]+)", url)
    if not file_key_match:
        return None, None
    file_key = file_key_match.group(1)

    node_id_match = re.search(r"node-id=([^&]+)", url)
    if not node_id_match:
        return file_key, None

    node_id = urllib.parse.unquote(node_id_match.group(1))
    return file_key, node_id


# ---------------------------------------------------------------------------
# Figma API helpers
# ---------------------------------------------------------------------------

def _api_get(url: str, token: str) -> Dict[str, Any]:
    req = urllib.request.Request(url)
    req.add_header("X-Figma-Token", token)
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise FigmaAPIError(e.code, body) from e
    except urllib.error.URLError as e:
        raise FigmaAPIError(0, str(e.reason)) from e


def fetch_file_structure(file_key: str, token: str) -> Dict[str, Any]:
    """Fetch file with depth=3 (pages + children + nested frames in sections)."""
    url = f"https://api.figma.com/v1/files/{file_key}?depth=3"
    return _api_get(url, token)


def fetch_node_children(file_key: str, node_id: str, token: str) -> Dict[str, Any]:
    """Fetch a specific node and its children."""
    url = f"https://api.figma.com/v1/files/{file_key}/nodes?ids={node_id}"
    return _api_get(url, token)


# ---------------------------------------------------------------------------
# Text extraction
# ---------------------------------------------------------------------------

def collect_text(node: Dict[str, Any]) -> List[str]:
    """Recursively collect all visible TEXT node characters."""
    if node.get("visible") is False:
        return []

    texts: List[str] = []
    if node.get("type") == "TEXT":
        chars = node.get("characters", "").strip()
        if chars:
            texts.append(chars)

    for child in node.get("children", []):
        texts.extend(collect_text(child))

    return texts


# ---------------------------------------------------------------------------
# State inference
# NOTE: extract_axure_page.py has its own _STATE_KEYWORDS with additional
#       Axure-specific states (login, popup). Update both if shared keywords change.
# ---------------------------------------------------------------------------

_STATE_KEYWORDS: List[Tuple[str, List[str]]] = [
    ("loading", ["loading", "skeleton", "載入", "讀取中"]),
    ("success", ["success", "data", "完成", "成功"]),
    ("empty", ["empty", "no data", "空", "無資料", "no result"]),
    ("error", ["error", "fail", "錯誤", "失敗", "exception"]),
]


def infer_state(frame_name: str) -> str:
    """Infer UI state from frame name keywords."""
    lower = frame_name.lower()
    for state, keywords in _STATE_KEYWORDS:
        for kw in keywords:
            if kw in lower:
                return state
    return "default"


# ---------------------------------------------------------------------------
# Page extraction
# ---------------------------------------------------------------------------

def find_page(
    document: Dict[str, Any],
    page_name: Optional[str],
    page_node_id: Optional[str],
) -> Optional[Dict[str, Any]]:
    """Find a page in the document by name or node-id."""
    pages = document.get("children", [])

    if page_node_id:
        canonical = page_node_id.replace("-", ":")
        for page in pages:
            if page.get("id", "").replace("-", ":") == canonical:
                return page

    if page_name:
        # Exact match first
        for page in pages:
            if page.get("name") == page_name:
                return page
        # Case-insensitive partial match
        lower_name = page_name.lower()
        for page in pages:
            if lower_name in page.get("name", "").lower():
                return page

    # If only one page exists, use it
    if len(pages) == 1:
        return pages[0]

    return None


def extract_frames(page: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract frames from a page node, recursing into SECTION and GROUP containers."""
    frames = []
    _CONTAINER_TYPES = ("SECTION", "GROUP")
    _FRAME_TYPES = ("FRAME", "COMPONENT", "COMPONENT_SET")

    for child in page.get("children", []):
        if child.get("visible") is False:
            continue
        node_type = child.get("type", "")

        # Recurse into containers to find nested frames
        if node_type in _CONTAINER_TYPES:
            frames.extend(extract_frames(child))
            continue

        if node_type not in _FRAME_TYPES:
            continue

        abs_box = child.get("absoluteBoundingBox", {})
        frame_info = {
            "id": child.get("id"),
            "name": child.get("name", ""),
            "type": node_type,
            "width": round(abs_box.get("width", 0)),
            "height": round(abs_box.get("height", 0)),
            "text_content": collect_text(child),
            "inferred_state": infer_state(child.get("name", "")),
        }
        frames.append(frame_info)

    return frames


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Extract all top-level frames from a Figma page for spec building."
    )
    parser.add_argument("url", help="Figma file or page URL")
    parser.add_argument(
        "--page",
        default=None,
        help="Page name to extract (required if file has multiple pages and URL has no node-id)",
    )
    parser.add_argument(
        "--token",
        default=None,
        help="Figma Access Token (also checks FIGMA_ACCESS_TOKEN env var and macOS Keychain)",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output JSON file path (default: .ai-artifacts/feature-spec-builder/figma_page.json)",
    )
    args = parser.parse_args()

    # Resolve default output path: .ai-artifacts/feature-spec-builder/figma_page.json
    if args.output is None:
        repo_root = _find_repo_root()
        args.output = str(repo_root / ".ai-artifacts" / "feature-spec-builder" / "figma_page.json")

    token = resolve_token(args.token)
    if not token:
        print(
            "Error: Figma Access Token not found.\n"
            "Checked: --token arg, FIGMA_ACCESS_TOKEN env var, macOS Keychain.\n"
            "Use keychain_helper.py store to save a token, or pass --token.",
            file=sys.stderr,
        )
        return 1

    file_key, node_id = parse_figma_url(args.url)
    if not file_key:
        print("Error: Could not parse file key from URL.", file=sys.stderr)
        return 1

    print(f"Fetching file structure for {file_key} ...")
    try:
        file_data = fetch_file_structure(file_key, token)
    except FigmaAPIError as e:
        if e.code == 429:
            print("Figma API rate limit (429). Please wait a moment and retry.", file=sys.stderr)
        elif e.code in (401, 403):
            print(f"Figma API auth error ({e.code}): token may be invalid or expired.", file=sys.stderr)
        else:
            print(str(e), file=sys.stderr)
        return 1
    document = file_data.get("document", {})

    page = find_page(document, args.page, node_id)
    if not page:
        available = [p.get("name") for p in document.get("children", [])]
        print(
            f"Error: Page not found. Available pages: {available}\n"
            f"Use --page to specify one.",
            file=sys.stderr,
        )
        return 1

    page_name = page.get("name", "Unknown")
    print(f"Extracting frames from page: {page_name}")

    frames = extract_frames(page)
    print(f"Found {len(frames)} top-level frame(s).")
    if not frames:
        print(
            "Warning: No frames found. The page may have deeply nested frames "
            "beyond depth=3. Try specifying a direct frame URL with node-id.",
            file=sys.stderr,
        )

    output = {
        "file_key": file_key,
        "page_name": page_name,
        "frame_count": len(frames),
        "frames": frames,
    }

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"Saved to {args.output}")

    cache_path = write_cache_metadata(
        args.output,
        source_type="figma",
        source_url=args.url,
        source_page=page_name,
        extractor_version=EXTRACTOR_VERSION,
    )
    print(f"Wrote cache metadata: {cache_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
