#!/usr/bin/env python3
"""Shared git/diff helpers for the forge-git-flow *branch-diff* skill family.

This module is the canonical entry point for any skill that needs to:
  - resolve a branch base commit (see :func:`resolve_branch_base`)
  - enumerate changed files / read unified diffs across a range
  - filter binary / generated / lockfile noise
  - group paths by Android module convention
  - estimate token budgets for chunked review

New branch-diff skills MUST prefer these helpers (either via direct import,
or via the ``branch_base.py`` CLI wrapper which returns JSON) instead of
re-implementing ``git merge-base`` inline. This keeps base-resolution
semantics — including BASE_COMMIT / BASE_REF env overrides and the
local-only refusal of ``origin/*`` refs — consistent across the suite.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Tuple, Dict, Any


def run(cmd: List[str], cwd: Optional[str] = None, check: bool = True) -> str:
    p = subprocess.run(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if check and p.returncode != 0:
        raise RuntimeError(f"Command failed ({p.returncode}): {' '.join(cmd)}\nSTDERR:\n{p.stderr}")
    return p.stdout.strip()


def is_git_repo() -> bool:
    try:
        run(["git", "rev-parse", "--is-inside-work-tree"])
        return True
    except Exception:
        return False


def current_branch() -> str:
    return run(["git", "rev-parse", "--abbrev-ref", "HEAD"])


def try_refs(refs: List[str]) -> List[str]:
    ok = []
    for r in refs:
        try:
            run(["git", "rev-parse", "--verify", r], check=True)
            ok.append(r)
        except Exception:
            pass
    return ok


def merge_base(a: str, b: str) -> str:
    return run(["git", "merge-base", a, b])


def head_commit() -> str:
    return run(["git", "rev-parse", "HEAD"])


def get_upstream_ref() -> Optional[str]:
    # Returns something like 'origin/feature-x' or None
    try:
        return run(["git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"], check=True)
    except Exception:
        return None


def get_remote_head_branch() -> Optional[str]:
    # best effort: detect origin/HEAD -> origin/main
    try:
        line = run(["git", "symbolic-ref", "refs/remotes/origin/HEAD"], check=True)
        return line.replace("refs/remotes/", "")
    except Exception:
        return None


def list_changed_files(base: str, head: str) -> List[Dict[str, Any]]:
    """
    Use --name-status for status and rename detection.
    Returns list with:
      {status, path, old_path?}
    """
    out = run(["git", "diff", "--name-status", "--find-renames", f"{base}..{head}"])
    files: List[Dict[str, Any]] = []
    if not out:
        return files
    for line in out.splitlines():
        parts = line.split("\t")
        status = parts[0]
        if status.startswith("R"):  # rename score e.g. R100
            files.append({"status": "R", "old_path": parts[1], "path": parts[2]})
        else:
            files.append({"status": status, "path": parts[1]})
    return files


def unified_diff(base: str, head: str, path: str) -> str:
    # Use -- to separate path; include minimal context? keep default context.
    return run(["git", "diff", f"{base}..{head}", "--", path], check=False)


def file_text_at(ref: str, path: str) -> Optional[str]:
    # Return None if file does not exist at ref
    try:
        return run(["git", "show", f"{ref}:{path}"], check=True)
    except Exception:
        return None


def is_probably_binary(text: str) -> bool:
    # Simple heuristic: contains NUL
    return "\x00" in text


def approx_tokens(text: str) -> int:
    # Rough heuristic: 1 token ~ 4 chars (English-ish). For CJK, tokens can be denser.
    # Still useful as a guardrail.
    return max(1, len(text) // 4)


def safe_mkdir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def write_text(p: Path, s: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(s, encoding="utf-8")


def write_json(p: Path, obj: Any) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


EXCLUDE_GLOBS = [
    "**/build/**",
    "**/.gradle/**",
    "**/.idea/**",
    "**/generated/**",
    "**/build/generated/**",
]

EXCLUDE_EXTS = {
    ".png", ".jpg", ".jpeg", ".webp", ".gif", ".mp4", ".mov", ".zip", ".jar", ".aar", ".keystore",
    ".aab", ".apk", ".so", ".dylib", ".dll", ".bin", ".pdf",
}


def is_excluded_path(path: str) -> bool:
    lp = path.lower()
    # ext filter
    ext = Path(lp).suffix
    if ext in EXCLUDE_EXTS:
        return True
    # glob-ish filter (very lightweight)
    for g in EXCLUDE_GLOBS:
        needle = g.replace("**/", "").replace("/**", "").replace("**", "")
        if needle and needle in lp:
            return True
    # lockfiles
    if Path(lp).name in {"yarn.lock", "package-lock.json", "pnpm-lock.yaml"}:
        return True
    return False


def group_key_for_path(path: str) -> str:
    """
    Heuristic grouping:
    - Gradle module: first segment if contains build.gradle(.kts) nearby? (too expensive)
      We'll use first path segment and special-case common multi-module layouts.
    """
    parts = path.split("/")
    if not parts:
        return "misc"
    top = parts[0]

    # Common Android multi-module conventions
    if top in {"app", "core", "data", "domain", "feature", "common", "shared"}:
        if top == "feature" and len(parts) >= 2:
            return f"feature/{parts[1]}"
        return top

    # If it looks like :module/src/...
    if len(parts) >= 2 and parts[1] == "src":
        return top

    return top


def resolve_branch_base() -> dict:
    """Resolve the branch base commit for diff range calculation.

    Priority: BASE_COMMIT env > BASE_REF env > auto-detect local main/master/develop.
    Remote-tracking refs are forbidden (local-only mode).
    """
    if not is_git_repo():
        raise SystemExit("Not inside a git repository.")

    br = current_branch()
    head = head_commit()

    base_commit_env = os.environ.get("BASE_COMMIT")
    if base_commit_env:
        return {
            "mode": "local-only",
            "current_branch": br,
            "head": head,
            "base_ref": None,
            "base_commit": base_commit_env,
            "range": f"{base_commit_env}..{head}",
            "notes": ["BASE_COMMIT provided; no ref resolution performed."],
        }

    remote_ref_re = re.compile(r"^(refs/remotes/|origin/|upstream/)", re.IGNORECASE)

    base_ref_env = os.environ.get("BASE_REF")
    if base_ref_env:
        if remote_ref_re.search(base_ref_env):
            raise SystemExit(f"Remote-tracking refs are forbidden in local-only mode: {base_ref_env}")
        try:
            run(["git", "rev-parse", "--verify", base_ref_env], check=True)
        except Exception:
            raise SystemExit(f"BASE_REF not found locally: {base_ref_env}")
        base_commit = merge_base(br, base_ref_env)
        return {
            "mode": "local-only",
            "current_branch": br,
            "head": head,
            "base_ref": base_ref_env,
            "base_commit": base_commit,
            "range": f"{base_commit}..{head}",
            "notes": ["BASE_REF provided; resolved via merge-base (local refs only)."],
        }

    candidates = ["main", "master", "develop"]
    existing = try_refs(candidates)

    info: dict = {
        "mode": "local-only",
        "current_branch": br,
        "head": head,
        "candidates": candidates,
        "existing_candidates": existing,
        "base_ref": None,
        "base_commit": None,
        "range": None,
        "notes": [],
    }

    if not existing:
        info["notes"].append(
            "Could not find local base refs (main|master|develop). "
            "Set BASE_REF=<local-branch-or-tag> or BASE_COMMIT=<sha>."
        )
        return info

    base_ref = existing[0]
    base_commit = merge_base(br, base_ref)
    info["base_ref"] = base_ref
    info["base_commit"] = base_commit
    info["range"] = f"{base_commit}..{head}"
    return info


PACKAGE_RE = re.compile(r"^\s*package\s+([a-zA-Z0-9_.]+)\s*$", re.MULTILINE)


def package_prefix(text: str) -> Optional[str]:
    m = PACKAGE_RE.search(text)
    if not m:
        return None
    pkg = m.group(1)
    segs = pkg.split(".")
    return ".".join(segs[:3]) if len(segs) >= 3 else pkg


def detect_sensitive_markers(diff_text: str) -> List[str]:
    markers = []
    patterns = [
        (r"AKIA[0-9A-Z]{16}", "Possible AWS Access Key"),
        (r"-----BEGIN (?:RSA|EC|OPENSSH) PRIVATE KEY-----", "Private key block"),
        (r"(?i)\b(api[_-]?key|secret|token|bearer)\b", "Generic secret/token keyword"),
    ]
    for rx, label in patterns:
        if re.search(rx, diff_text):
            markers.append(label)
    return markers
