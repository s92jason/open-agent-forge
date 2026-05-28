#!/usr/bin/env python3
"""
Manage Figma access token and Axure access codes in a secure local store.

Storage backend is selected automatically:
  - macOS  -> macOS Keychain (via the `security` CLI)
  - others -> a 0600-permission JSON file under
              ${XDG_DATA_HOME:-~/.local/share}/feature-spec-builder/secrets.json

Credentials are never written into the repo, the spec, or any output text.

Figma commands:
    store           Read Figma token from stdin and save to the secret store.
    get             Print Figma token to stdout (exit 0 = found, exit 1 = not found).
    check           Check if Figma token exists (exit 0 = yes, exit 1 = no). Never prints the token.
    delete          Remove Figma token from the secret store.

Axure commands:
    axure-store     Store an Axure access code for a share link.
    axure-get       Get an Axure access code for a share link (prints to stdout).
    axure-check     Check if an Axure access code exists for a share link.
    axure-delete    Remove an Axure access code for a share link.

Usage:
    echo "figd_xxx" | python3 keychain_helper.py store
    python3 keychain_helper.py check
    python3 keychain_helper.py delete

    echo "mycode" | python3 keychain_helper.py axure-store --link "https://share.axure.com/xxx"
    python3 keychain_helper.py axure-get --link "https://share.axure.com/xxx"
    python3 keychain_helper.py axure-check --link "https://share.axure.com/xxx"
    python3 keychain_helper.py axure-delete --link "https://share.axure.com/xxx"
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

SERVICE = "com.claude.feature-spec-builder"
ACCOUNT_FIGMA = "figma_access_token"
ACCOUNT_AXURE = "axure_access_codes"


# ---------------------------------------------------------------------------
# Backend selection
# ---------------------------------------------------------------------------

def _use_keychain() -> bool:
    """Use macOS Keychain only when on Darwin and the `security` CLI exists."""
    return sys.platform == "darwin" and shutil.which("security") is not None


def store_label() -> str:
    """Human-readable name of the active backend, for user-facing messages."""
    if _use_keychain():
        return "macOS Keychain"
    return f"local secret store ({_secrets_file()})"


# ---------------------------------------------------------------------------
# macOS Keychain backend
# ---------------------------------------------------------------------------

def _run_security(args: list[str]) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            ["security", *args],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return subprocess.CompletedProcess(args, returncode=1, stdout="", stderr="")


def _keychain_read(account: str) -> str | None:
    result = _run_security(
        ["find-generic-password", "-s", SERVICE, "-a", account, "-w"],
    )
    if result.returncode == 0:
        return result.stdout.strip() or None
    return None


def _keychain_write(account: str, value: str) -> bool:
    """Write a value to Keychain (overwrite if exists). Returns True on success.

    Known limitation: macOS `security add-generic-password -w` passes the value
    as a CLI argument, which is briefly visible in process listings (ps aux).
    This is a constraint of Apple's security CLI — no stdin alternative exists.
    """
    _run_security(["delete-generic-password", "-s", SERVICE, "-a", account])
    result = _run_security(
        ["add-generic-password", "-s", SERVICE, "-a", account, "-w", value],
    )
    return result.returncode == 0


def _keychain_delete(account: str) -> bool:
    result = _run_security(
        ["delete-generic-password", "-s", SERVICE, "-a", account],
    )
    return result.returncode == 0


def _keychain_exists(account: str) -> bool:
    result = _run_security(
        ["find-generic-password", "-s", SERVICE, "-a", account],
    )
    return result.returncode == 0


# ---------------------------------------------------------------------------
# File backend (non-macOS): 0600 JSON under the XDG data dir
# ---------------------------------------------------------------------------

def _secrets_file() -> Path:
    base = os.environ.get("XDG_DATA_HOME") or os.path.join(
        os.path.expanduser("~"), ".local", "share"
    )
    return Path(base) / "feature-spec-builder" / "secrets.json"


def _file_load() -> dict:
    path = _secrets_file()
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def _file_save(data: dict) -> bool:
    path = _secrets_file()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        os.chmod(path.parent, 0o700)
        fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False)
        os.chmod(path, 0o600)
        return True
    except OSError as exc:
        print(f"Error: failed to write secret store: {exc}", file=sys.stderr)
        return False


def _file_read(account: str) -> str | None:
    value = _file_load().get(account)
    return value or None


def _file_write(account: str, value: str) -> bool:
    data = _file_load()
    data[account] = value
    return _file_save(data)


def _file_delete(account: str) -> bool:
    data = _file_load()
    if account not in data:
        return False
    del data[account]
    if not data:
        try:
            _secrets_file().unlink()
            return True
        except OSError:
            return False
    return _file_save(data)


def _file_exists(account: str) -> bool:
    return account in _file_load()


# ---------------------------------------------------------------------------
# Backend-dispatching secret API (rest of the module calls these)
# ---------------------------------------------------------------------------

def _secret_read(account: str) -> str | None:
    return _keychain_read(account) if _use_keychain() else _file_read(account)


def _secret_write(account: str, value: str) -> bool:
    return _keychain_write(account, value) if _use_keychain() else _file_write(account, value)


def _secret_delete(account: str) -> bool:
    return _keychain_delete(account) if _use_keychain() else _file_delete(account)


def _secret_exists(account: str) -> bool:
    return _keychain_exists(account) if _use_keychain() else _file_exists(account)


# ---------------------------------------------------------------------------
# Figma token commands
# ---------------------------------------------------------------------------

def store_token() -> int:
    """Read Figma token from stdin and store in Keychain."""
    token = sys.stdin.read().strip()
    if not token:
        print("Error: No token provided on stdin.", file=sys.stderr)
        return 1
    if len(token) < 10:
        print("Error: Token looks too short to be valid (expected 40+ chars).", file=sys.stderr)
        return 1

    if _secret_write(ACCOUNT_FIGMA, token):
        print(f"Figma token saved to {store_label()}.")
        return 0
    else:
        print(f"Error: Failed to store token in {store_label()}.", file=sys.stderr)
        return 1


def get_token() -> int:
    """Print Figma token to stdout. Exit 0 = found, exit 1 = not found."""
    token = _secret_read(ACCOUNT_FIGMA)
    if token:
        print(token)
        return 0
    else:
        print(f"No Figma token in {store_label()}.", file=sys.stderr)
        return 1


def check_token() -> int:
    """Check if Figma token exists. Exit 0 = exists, exit 1 = not found."""
    if _secret_exists(ACCOUNT_FIGMA):
        print(f"Figma token found in {store_label()}.")
        return 0
    else:
        print(f"No Figma token in {store_label()}.")
        return 1


def delete_token() -> int:
    """Remove Figma token from the active secret store."""
    if _secret_delete(ACCOUNT_FIGMA):
        print(f"Figma token removed from {store_label()}.")
        return 0
    else:
        print("No Figma token found to remove.")
        return 1


# ---------------------------------------------------------------------------
# Link normalization
# ---------------------------------------------------------------------------

def _normalize_link(link: str) -> str:
    """Normalize a share link for comparison (strip scheme, trailing slash, lowercase)."""
    link = link.strip().rstrip("/").lower()
    link = re.sub(r"^https?://", "", link)
    return link


# ---------------------------------------------------------------------------
# Axure access code commands (stored as JSON mapping in one Keychain entry)
# ---------------------------------------------------------------------------

def _load_axure_codes() -> dict[str, str]:
    """Load the share_link -> access_code mapping from the active store."""
    raw = _secret_read(ACCOUNT_AXURE)
    if raw:
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {}
    return {}


def _save_axure_codes(codes: dict[str, str]) -> bool:
    """Save the share_link -> access_code mapping to the active store."""
    return _secret_write(ACCOUNT_AXURE, json.dumps(codes, ensure_ascii=False))


def axure_store(link: str) -> int:
    """Read access code from stdin and store for the given share link."""
    code = sys.stdin.read().strip()
    if not code:
        print("Error: No access code provided on stdin.", file=sys.stderr)
        return 1

    codes = _load_axure_codes()
    codes[link] = code
    if _save_axure_codes(codes):
        print(f"Axure access code saved for: {link}")
        return 0
    else:
        print("Error: Failed to save Axure access code.", file=sys.stderr)
        return 1


def axure_get(link: str) -> int:
    """Print the access code for a share link to stdout."""
    codes = _load_axure_codes()
    # Exact match first
    code = codes.get(link)
    if code:
        print(code)
        return 0
    # Normalized fallback (trailing slash, case, scheme differences)
    normalized = _normalize_link(link)
    for stored_link, stored_code in codes.items():
        if _normalize_link(stored_link) == normalized:
            print(stored_code)
            return 0
    print(f"No access code found for: {link}", file=sys.stderr)
    return 1


def axure_check(link: str) -> int:
    """Check if an access code exists for a share link. Exit 0 = exists, exit 1 = not found."""
    codes = _load_axure_codes()
    if link in codes:
        print(f"Axure access code found for: {link}")
        return 0
    normalized = _normalize_link(link)
    for stored_link in codes:
        if _normalize_link(stored_link) == normalized:
            print(f"Axure access code found for: {link}")
            return 0
    print(f"No Axure access code for: {link}")
    return 1


def axure_delete(link: str) -> int:
    """Remove the access code for a share link."""
    codes = _load_axure_codes()
    if link not in codes:
        print(f"No Axure access code found for: {link}")
        return 1
    del codes[link]
    success = _save_axure_codes(codes) if codes else _secret_delete(ACCOUNT_AXURE)
    if not success:
        print(f"Error: Failed to update {store_label()} after deletion.", file=sys.stderr)
        return 1
    print(f"Axure access code removed for: {link}")
    return 0


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Manage Figma token and Axure access codes in a secure local store "
        "(macOS Keychain, or a 0600 file on other platforms)."
    )
    parser.add_argument(
        "command",
        choices=["store", "get", "check", "delete", "axure-store", "axure-get", "axure-check", "axure-delete"],
    )
    parser.add_argument(
        "--link",
        default=None,
        help="Axure share link (required for axure-* commands)",
    )
    args = parser.parse_args()

    # Axure commands require --link
    if args.command.startswith("axure-") and not args.link:
        print("Error: --link is required for axure commands.", file=sys.stderr)
        return 1

    figma_commands = {
        "store": store_token,
        "get": get_token,
        "check": check_token,
        "delete": delete_token,
    }
    axure_commands = {
        "axure-store": axure_store,
        "axure-get": axure_get,
        "axure-check": axure_check,
        "axure-delete": axure_delete,
    }

    if args.command in figma_commands:
        return figma_commands[args.command]()
    else:
        return axure_commands[args.command](args.link)


if __name__ == "__main__":
    raise SystemExit(main())
