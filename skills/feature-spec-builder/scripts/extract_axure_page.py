#!/usr/bin/env python3
"""
Extract page structure and text content from an Axure Cloud (axshare.com) prototype.

Supports access-code-protected prototypes via SHA-512 hashed authentication.
Access codes are read from macOS Keychain (via keychain_helper.py) or stdin.

Outputs a spec-oriented JSON with sitemap, page list, and text content per page.

Usage:
    # With access code from Keychain (previously stored via keychain_helper.py axure-store):
    python3 extract_axure_page.py "https://abc123.axshare.com/"

    # With access code via --code argument:
    python3 extract_axure_page.py "https://abc123.axshare.com/" --code "myAccessCode"

    # Custom output path (default: .ai-artifacts/feature-spec-builder/axure_data.json):
    python3 extract_axure_page.py "https://abc123.axshare.com/" --output path/to/axure_data.json
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from http.cookiejar import CookieJar
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from cache_helper import write_cache_metadata

EXTRACTOR_VERSION = "1.0"

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
# Constants
# ---------------------------------------------------------------------------

_SCRIPT_DIR = Path(__file__).resolve().parent
_KEYCHAIN_HELPER = _SCRIPT_DIR / "keychain_helper.py"

# ---------------------------------------------------------------------------
# Keychain helpers (delegate to keychain_helper.py)
# ---------------------------------------------------------------------------


def _read_axure_code_from_keychain(share_link: str) -> Optional[str]:
    """Read Axure access code for a share link via keychain_helper.py axure-get."""
    try:
        result = subprocess.run(
            [sys.executable, str(_KEYCHAIN_HELPER), "axure-get", "--link", share_link],
            capture_output=True, text=True, check=False,
        )
        if result.returncode == 0:
            return result.stdout.strip() or None
    except FileNotFoundError:
        pass
    return None


# ---------------------------------------------------------------------------
# URL parsing
# ---------------------------------------------------------------------------


def parse_axshare_url(url: str) -> Tuple[Optional[str], Optional[str]]:
    """Extract project ID and optional page ID from an axshare.com URL.

    Supports:
        https://abc123.axshare.com/
        https://abc123.axshare.com/page.html
        https://abc123.axshare.com/?id=e5a7id
        http://abc123.axshare.com/#p=page&id=abc123

    Returns (project_id, page_id) tuple.
    """
    project_match = re.search(r"([a-zA-Z0-9]+)\.axshare\.com", url)
    if not project_match:
        return None, None

    project_id = project_match.group(1)

    # Extract page ID from ?id= or &id= query parameter
    page_id = None
    id_match = re.search(r"[?&]id=([a-zA-Z0-9]+)", url)
    if id_match:
        page_id = id_match.group(1)

    return project_id, page_id


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------


def _build_opener() -> Tuple[urllib.request.OpenerDirector, CookieJar]:
    """Build a urllib opener with cookie support."""
    cookie_jar = CookieJar()
    cookie_handler = urllib.request.HTTPCookieProcessor(cookie_jar)
    opener = urllib.request.build_opener(cookie_handler)
    opener.addheaders = [
        (
            "User-Agent",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        ),
    ]
    return opener, cookie_jar


def _fetch(
    opener: urllib.request.OpenerDirector,
    url: str,
    data: Optional[bytes] = None,
    content_type: Optional[str] = None,
    extra_headers: Optional[Dict[str, str]] = None,
) -> Tuple[int, str]:
    """Fetch a URL, returning (status_code, body)."""
    req = urllib.request.Request(url, data=data)
    if content_type:
        req.add_header("Content-Type", content_type)
    if extra_headers:
        for key, value in extra_headers.items():
            req.add_header(key, value)
    if data:
        req.method = "POST"
    try:
        with opener.open(req, timeout=30) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        return e.code, body
    except urllib.error.URLError as e:
        return 0, str(e.reason)


# ---------------------------------------------------------------------------
# Axure authentication
# ---------------------------------------------------------------------------


def _extract_json_object(text: str, marker: str) -> Optional[Dict[str, Any]]:
    """Find the innermost complete JSON object containing *marker* using bracket matching."""
    pos = text.find(marker)
    if pos == -1:
        return None
    # Walk backwards to find the nearest opening brace
    brace = text.rfind("{", 0, pos)
    if brace == -1:
        return None
    # Walk forward with depth counting to find the matching closing brace
    depth = 0
    for i in range(brace, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
        if depth == 0:
            try:
                return json.loads(text[brace : i + 1])
            except json.JSONDecodeError:
                return None
    return None


def _sha512_hex(text: str) -> str:
    """SHA-512 hash as lowercase hex string (matches Axure's hex_sha512)."""
    return hashlib.sha512(text.encode("utf-8")).hexdigest()


def authenticate(
    opener: urllib.request.OpenerDirector,
    project_id: str,
    access_code: str,
) -> bool:
    """Authenticate with Axure Cloud using access code.

    Returns True if authentication succeeded.
    """
    base_url = f"https://{project_id}.axshare.com"
    login_url = f"{base_url}/prototype/dologin/{project_id.upper()}"

    hashed_password = _sha512_hex(access_code)

    payload = urllib.parse.urlencode(
        {
            "Password": hashed_password,
            "currenthost": f"{project_id}.axshare.com",
            "navigateQuery": "",
            "path": "",
            "isAjax": "true",
        }
    )

    status, body = _fetch(
        opener,
        login_url,
        data=payload.encode("utf-8"),
        content_type="application/x-www-form-urlencoded",
        extra_headers={
            "X-Requested-With": "XMLHttpRequest",
            "Referer": f"{base_url}/prototype/login/{project_id.upper()}",
            "Origin": base_url,
        },
    )

    if status != 200:
        print(f"Auth request failed with status {status}", file=sys.stderr)
        return False

    # Parse JSON response
    try:
        resp_data = json.loads(body)
    except json.JSONDecodeError:
        # Might be HTML — extract the JSON object containing "success" via bracket matching
        resp_data = _extract_json_object(body, '"success"')
        if resp_data is None:
            print("Auth response is not JSON.", file=sys.stderr)
            return False

    if resp_data.get("success"):
        # Extract and set auth cookie if provided in response
        data_vars = resp_data.get("data", {}).get("Vars", {})
        cookie_string = data_vars.get("authCookieString", "")
        if cookie_string and "=" in cookie_string:
            cookie_name, cookie_value = cookie_string.split("=", 1)
            # Manually inject cookie into the jar
            from http.cookiejar import Cookie
            import time

            cookie = Cookie(
                version=0,
                name=cookie_name.strip(),
                value=cookie_value.strip(),
                port=None,
                port_specified=False,
                domain=f".{project_id}.axshare.com",
                domain_specified=True,
                domain_initial_dot=True,
                path="/",
                path_specified=True,
                secure=True,
                expires=int(time.time()) + 90 * 24 * 3600,
                discard=False,
                comment=None,
                comment_url=None,
                rest={"SameSite": "None"},
            )
            # Add cookie to the cookie jar
            for handler in opener.handlers:
                if hasattr(handler, "cookiejar"):
                    handler.cookiejar.set_cookie(cookie)
                    break
        print("Authentication successful.", file=sys.stderr)
        return True
    else:
        msg = resp_data.get("message", "Unknown error")
        print(f"Authentication failed: {msg}", file=sys.stderr)
        return False


def check_no_auth_needed(
    opener: urllib.request.OpenerDirector,
    project_id: str,
) -> bool:
    """Check if the prototype is accessible without authentication."""
    base_url = f"https://{project_id}.axshare.com"
    status, body = _fetch(opener, base_url)

    # If we get a 200 with actual prototype content (not login page)
    if status == 200:
        if "prototype/login" not in body.lower() and (
            "axure" in body.lower() or "mainFrame" in body.lower()
        ):
            return True
    return False


# ---------------------------------------------------------------------------
# Content extraction
# ---------------------------------------------------------------------------


def fetch_document_js(
    opener: urllib.request.OpenerDirector,
    project_id: str,
) -> Optional[str]:
    """Fetch data/document.js which contains the sitemap and configuration."""
    base_url = f"https://{project_id}.axshare.com"
    status, body = _fetch(opener, f"{base_url}/data/document.js")
    if status == 200 and "$axure.loadDocument" in body:
        return body
    # Try alternate path
    status, body = _fetch(opener, f"{base_url}/document.js")
    if status == 200 and "$axure.loadDocument" in body:
        return body
    return None


def parse_sitemap(document_js: str) -> List[Dict[str, Any]]:
    """Parse sitemap.rootNodes from document.js content.

    Axure uses a compressed format where short variable names map to values:
        var v="id",w="abc",x="pageName",y="Page Title",z="type",A="Wireframe",B="url",C="page.html"
    And constructs objects via a helper: _(v,w,x,y,z,A,B,C) → {id:"abc", pageName:"Page Title", ...}

    Strategy:
    1. Extract all variable definitions into a mapping
    2. Find the _creator function body and locate rootNodes array
    3. Resolve variable references to reconstruct page entries
    """
    # Strategy 1: Parse the compressed variable format
    pages = _parse_compressed_format(document_js)
    if pages:
        return pages

    # Strategy 2: Try direct JSON-like parsing (uncompressed format)
    match = re.search(r"\$axure\.loadDocument\s*\(\s*(\{.*\})\s*\)", document_js, re.DOTALL)
    if match:
        raw = match.group(1)
        sitemap_match = re.search(r"rootNodes\s*:\s*(\[.*?\])\s*\}", raw, re.DOTALL)
        if sitemap_match:
            nodes_str = sitemap_match.group(1)
            nodes_str = re.sub(r"(\w+)\s*:", r'"\1":', nodes_str)
            nodes_str = re.sub(r",\s*([}\]])", r"\1", nodes_str)
            nodes_str = nodes_str.replace("'", '"')
            try:
                nodes = json.loads(nodes_str)
                return _flatten_nodes(nodes)
            except json.JSONDecodeError:
                return _regex_extract_pages(nodes_str)

    return []


def _parse_compressed_format(document_js: str) -> List[Dict[str, Any]]:
    """Parse Axure's compressed variable format in document.js.

    Axure compresses document.js like:
        var _ = function() { ... }  // helper: takes alternating k,v pairs → object
        var _creator = function() { return _(b,_(c,d,...),t,_(u,[_(v,w,x,y,z,A,B,C)])); };
        var b="configuration", ..., v="id", w="k08r6q", x="pageName", y="Page Title",
            z="type", A="Wireframe", B="url", C="page.html", ...

    The rootNodes array looks like: _(u,[_(v,w,x,y,z,A,B,C), _(v,w2,x,y2,...)])
    where u="rootNodes", v="id", x="pageName", z="type", B="url" are property keys
    and w, y, A, C are the corresponding values.
    """
    # Step 1: Extract ALL variable assignments from the document
    # They appear as: varname="string" or varname=0xFF or varname=123 or varname=true
    var_map: Dict[str, Any] = {}
    assign_pattern = re.compile(
        r'(?:^|,|\s)([a-zA-Z_]\w*)\s*=\s*("([^"]*)"|0x[0-9a-fA-F]+|[\d.]+|true|false|null)'
    )
    for m in assign_pattern.finditer(document_js):
        var_name = m.group(1)
        raw_value = m.group(2)
        if raw_value.startswith('"'):
            var_map[var_name] = m.group(3)
        elif raw_value.startswith("0x"):
            var_map[var_name] = int(raw_value, 16)
        elif raw_value in ("true", "false"):
            var_map[var_name] = raw_value == "true"
        elif raw_value == "null":
            var_map[var_name] = None
        elif "." in raw_value:
            var_map[var_name] = float(raw_value)
        else:
            var_map[var_name] = int(raw_value)

    # Step 2: Find key property-name variables
    pagename_var = None
    url_var = None
    id_var = None
    type_var = None
    children_var = None
    for vn, vv in var_map.items():
        if vv == "pageName":
            pagename_var = vn
        elif vv == "url":
            url_var = vn
        elif vv == "id":
            id_var = vn
        elif vv == "type":
            type_var = vn
        elif vv == "children":
            children_var = vn

    if not pagename_var or not url_var:
        return []

    # Step 3: Find ALL _() calls in the document that contain pageName_var
    # Since Axure nests page entries inside arrays like [_(v,w,x,y,z,A,B,C)],
    # we scan the entire document for _() calls with pageName_var as a direct arg.
    pages = _find_all_page_calls(document_js, var_map, pagename_var, children_var)
    return pages


def _find_all_page_calls(
    text: str,
    var_map: Dict[str, Any],
    pagename_var: str,
    children_var: Optional[str],
) -> List[Dict[str, Any]]:
    """Find all _() calls containing pageName variable and resolve them to page entries.

    Scans character by character, advancing by 1 each time (not skipping past
    matched calls), so nested _() calls inside [...] are also found.
    """
    pages = []
    i = 0
    while i < len(text) - 1:
        if text[i:i+2] == "_(" and (i == 0 or not text[i-1].isalnum()):
            start = i + 2
            depth = 1
            j = start
            while j < len(text) and depth > 0:
                if text[j] == "(":
                    depth += 1
                elif text[j] == ")":
                    depth -= 1
                j += 1
            inner = text[start:j-1]
            args = _split_args(inner)

            if pagename_var in args:
                entry = _resolve_entry(args, var_map)
                if "pageName" in entry:
                    page = {
                        "id": str(entry.get("id", "")),
                        "pageName": str(entry.get("pageName", "")),
                        "type": str(entry.get("type", "")),
                        "url": str(entry.get("url", "")),
                        "depth": 0,
                    }
                    pages.append(page)
            # Advance by 1 (not j) — intentional.
            # Axure nests page entries inside outer _() calls:
            #   _(config, _(rootNodes, [_(id,w,pageName,y,...), ...]))
            # Jumping to j would skip past the outer _() and miss all
            # nested page _() calls inside it. Stepping by 1 ensures
            # every nested _( is visited. Performance is acceptable
            # since document.js is typically tens of KB (milliseconds).
            i += 1
        else:
            i += 1
    return pages


def _resolve_entry(args: List[str], var_map: Dict[str, Any]) -> Dict[str, Any]:
    """Resolve alternating key-value args into a dict using the variable map."""
    entry: Dict[str, Any] = {}
    i = 0
    while i < len(args) - 1:
        key_ref = args[i].strip()
        val_ref = args[i + 1].strip()

        key = var_map.get(key_ref, key_ref)
        if not isinstance(key, str):
            i += 2
            continue

        # Skip nested structures
        if val_ref.startswith("_(") or val_ref.startswith("["):
            i += 2
            continue

        val = var_map.get(val_ref, val_ref)
        entry[key] = val
        i += 2

    return entry


def _split_args(args_str: str) -> List[str]:
    """Split comma-separated arguments, respecting nested parentheses and brackets."""
    result = []
    depth = 0
    current: List[str] = []
    for ch in args_str:
        if ch in ("(", "["):
            depth += 1
            current.append(ch)
        elif ch in (")", "]"):
            depth -= 1
            current.append(ch)
        elif ch == "," and depth == 0:
            result.append("".join(current).strip())
            current = []
        else:
            current.append(ch)
    if current:
        result.append("".join(current).strip())
    return result


def _flatten_nodes(
    nodes: List[Dict[str, Any]], depth: int = 0
) -> List[Dict[str, Any]]:
    """Flatten nested sitemap nodes into a flat list with depth info."""
    result = []
    for node in nodes:
        entry = {
            "id": node.get("id", ""),
            "pageName": node.get("pageName", node.get("page", "")),
            "type": node.get("type", ""),
            "url": node.get("url", ""),
            "depth": depth,
        }
        result.append(entry)
        children = node.get("children", [])
        if children:
            result.extend(_flatten_nodes(children, depth + 1))
    return result


def _regex_extract_pages(text: str) -> List[Dict[str, Any]]:
    """Fallback: extract page info from JS text using regex."""
    pages = []
    # Match patterns like: {id:"xxx", pageName:"Page Name", type:"Axure:Page", url:"page.html"}
    pattern = re.compile(
        r'"id"\s*:\s*"([^"]*)".*?"pageName"\s*:\s*"([^"]*)".*?"url"\s*:\s*"([^"]*)"',
        re.DOTALL,
    )
    for m in pattern.finditer(text):
        pages.append(
            {
                "id": m.group(1),
                "pageName": m.group(2),
                "type": "Axure:Page",
                "url": m.group(3),
                "depth": 0,
            }
        )
    return pages


def fetch_page_content(
    opener: urllib.request.OpenerDirector,
    project_id: str,
    page_url: str,
) -> Optional[str]:
    """Fetch a specific page HTML file from the prototype."""
    base_url = f"https://{project_id}.axshare.com"
    # Ensure page_url doesn't start with /
    page_url = page_url.lstrip("/")
    # URL-encode non-ASCII characters (e.g., Chinese page names)
    encoded_url = urllib.parse.quote(page_url, safe="/:?&=#")
    status, body = _fetch(opener, f"{base_url}/{encoded_url}")
    if status == 200:
        return body
    return None


def extract_text_from_html(html_content: str) -> List[str]:
    """Extract visible text content from Axure page HTML.

    Axure pages contain widget text in various formats:
    - <p> and <span> tags with text content
    - data-label attributes
    - Text in script-generated widget definitions
    """
    texts = []

    # Extract text from HTML tags (p, span, div, a, h1-h6, li, td, th, label, button)
    tag_pattern = re.compile(
        r"<(?:p|span|div|a|h[1-6]|li|td|th|label|button)[^>]*>(.*?)</(?:p|span|div|a|h[1-6]|li|td|th|label|button)>",
        re.DOTALL | re.IGNORECASE,
    )
    for m in tag_pattern.finditer(html_content):
        text = _clean_html(m.group(1))
        if text and len(text) > 1:
            texts.append(text)

    # Extract data-label attributes
    label_pattern = re.compile(r'data-label="([^"]+)"')
    for m in label_pattern.finditer(html_content):
        text = html.unescape(m.group(1)).strip()
        if text and len(text) > 1:
            texts.append(text)

    # Extract text from Axure widget definitions in scripts
    # Pattern: text:"Some text" or label:"Some text"
    widget_text_pattern = re.compile(r'(?:text|label)\s*:\s*"([^"]+)"')
    for m in widget_text_pattern.finditer(html_content):
        text = m.group(1).strip()
        if text and len(text) > 1 and not text.startswith("$"):
            texts.append(text)

    # Deduplicate while preserving order
    seen = set()
    unique_texts = []
    for t in texts:
        if t not in seen:
            seen.add(t)
            unique_texts.append(t)

    return unique_texts


def _clean_html(text: str) -> str:
    """Remove HTML tags and decode entities."""
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


# ---------------------------------------------------------------------------
# State inference
# NOTE: extract_figma_page.py has its own _STATE_KEYWORDS (Figma frame names).
#       This version adds Axure-specific states (login, popup). Update both if shared keywords change.
# ---------------------------------------------------------------------------

_STATE_KEYWORDS: List[Tuple[str, List[str]]] = [
    ("loading", ["loading", "skeleton", "載入", "讀取中", "spinner"]),
    ("success", ["success", "data", "完成", "成功", "result"]),
    ("empty", ["empty", "no data", "空", "無資料", "no result", "blank"]),
    ("error", ["error", "fail", "錯誤", "失敗", "exception", "404", "timeout"]),
    ("login", ["login", "登入", "sign in", "password", "密碼"]),
    ("popup", ["popup", "modal", "dialog", "彈窗", "對話框", "alert"]),
]


def infer_state(page_name: str) -> str:
    """Infer UI state from page name keywords."""
    lower = page_name.lower()
    for state, keywords in _STATE_KEYWORDS:
        for kw in keywords:
            if kw in lower:
                return state
    return "default"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Extract page structure and content from Axure Cloud (axshare.com) prototypes."
    )
    parser.add_argument("url", help="Axure share URL (e.g., https://abc123.axshare.com/)")
    parser.add_argument(
        "--code",
        default=None,
        help="Access code (also checks AXURE_ACCESS_CODE env var and the local secret store)",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output JSON file path (default: .ai-artifacts/feature-spec-builder/axure_data.json)",
    )
    parser.add_argument(
        "--pages-limit",
        type=int,
        default=50,
        help="Max number of pages to fetch content for (default: 50)",
    )
    args = parser.parse_args()

    # Resolve default output path: .ai-artifacts/feature-spec-builder/axure_data.json
    if args.output is None:
        repo_root = _find_repo_root()
        args.output = str(repo_root / ".ai-artifacts" / "feature-spec-builder" / "axure_data.json")

    # Parse URL
    project_id, target_page_id = parse_axshare_url(args.url)
    if not project_id:
        print(
            "Error: Could not parse project ID from URL.\n"
            "Expected format: https://<id>.axshare.com/",
            file=sys.stderr,
        )
        return 1

    print(f"Project ID: {project_id}", file=sys.stderr)
    if target_page_id:
        print(f"Target page ID: {target_page_id}", file=sys.stderr)

    # Build HTTP client with cookie support
    opener, cookie_jar = _build_opener()

    # Resolve access code (priority: --code arg > AXURE_ACCESS_CODE env > secret store)
    access_code = args.code
    if not access_code:
        access_code = os.environ.get("AXURE_ACCESS_CODE")
    if not access_code:
        access_code = _read_axure_code_from_keychain(args.url)

    # Try without auth first
    if not access_code:
        if check_no_auth_needed(opener, project_id):
            print("Prototype is publicly accessible (no access code needed).", file=sys.stderr)
        else:
            print(
                "Error: Access code required but not provided.\n"
                "Provide via --code, the AXURE_ACCESS_CODE env var, or store with:\n"
                f'  echo "<code>" | python3 keychain_helper.py axure-store --link "{args.url}"',
                file=sys.stderr,
            )
            return 1
    else:
        print("Authenticating with access code...", file=sys.stderr)
        if not authenticate(opener, project_id, access_code):
            print(
                "Error: Authentication failed. Check your access code.",
                file=sys.stderr,
            )
            return 1

    # Fetch document.js for sitemap
    print("Fetching document.js (sitemap)...", file=sys.stderr)
    doc_js = fetch_document_js(opener, project_id)
    if not doc_js:
        print(
            "Error: Could not fetch document.js. "
            "The prototype may use a different structure or the access code may be wrong.",
            file=sys.stderr,
        )
        return 1

    # Parse sitemap
    all_pages = parse_sitemap(doc_js)
    print(f"Found {len(all_pages)} page(s) in sitemap.", file=sys.stderr)

    # Filter by target page ID if specified
    if target_page_id and all_pages:
        filtered = [p for p in all_pages if p.get("id") == target_page_id]
        if filtered:
            pages = filtered
            print(f"Filtered to target page: {pages[0].get('pageName', target_page_id)}", file=sys.stderr)
        else:
            # Show available pages to help user find the right ID
            print(f"Warning: Page ID '{target_page_id}' not found. Available pages:", file=sys.stderr)
            for p in all_pages:
                print(f"  - id={p.get('id')}  name={p.get('pageName')}", file=sys.stderr)
            pages = all_pages
    else:
        pages = all_pages

    if not pages:
        # Even if we can't parse the sitemap, output what we have
        print(
            "Warning: Could not parse sitemap from document.js. "
            "Outputting raw document.js content for manual analysis.",
            file=sys.stderr,
        )
        output = {
            "project_id": project_id,
            "url": args.url,
            "page_count": 0,
            "pages": [],
            "raw_document_js": doc_js[:10000],  # Truncate for safety
        }
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        print(f"Saved (partial) to {args.output}", file=sys.stderr)
        return 0

    # Fetch content for each page
    pages_with_content = []
    fetch_count = min(len(pages), args.pages_limit)
    for i, page in enumerate(pages[:fetch_count]):
        page_url = page.get("url", "")
        page_name = page.get("pageName", f"page_{i}")
        if not page_url:
            pages_with_content.append(
                {**page, "text_content": [], "inferred_state": infer_state(page_name)}
            )
            continue

        print(
            f"  [{i + 1}/{fetch_count}] Fetching: {page_name} ({page_url})",
            file=sys.stderr,
        )
        page_html = fetch_page_content(opener, project_id, page_url)
        text_content = extract_text_from_html(page_html) if page_html else []
        pages_with_content.append(
            {
                **page,
                "text_content": text_content,
                "inferred_state": infer_state(page_name),
            }
        )

    if len(pages) > fetch_count:
        print(
            f"Note: Only fetched {fetch_count} of {len(pages)} pages. "
            f"Use --pages-limit to increase.",
            file=sys.stderr,
        )

    # Build output
    output = {
        "project_id": project_id,
        "url": args.url,
        "page_count": len(pages),
        "pages_fetched": fetch_count,
        "pages": pages_with_content,
    }

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"Saved to {args.output}", file=sys.stderr)

    cache_path = write_cache_metadata(
        args.output,
        source_type="axure",
        source_url=args.url,
        extractor_version=EXTRACTOR_VERSION,
    )
    print(f"Wrote cache metadata: {cache_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
