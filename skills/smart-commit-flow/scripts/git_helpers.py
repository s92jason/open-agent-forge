from __future__ import annotations

import subprocess
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class CmdResult:
    code: int
    stdout: str
    stderr: str


def run(cmd: List[str], cwd: Optional[str] = None) -> CmdResult:
    """
    Run a command and capture stdout/stderr as UTF-8 text.
    Intentionally minimal and deterministic.
    """
    p = subprocess.run(
        cmd,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return CmdResult(p.returncode, p.stdout, p.stderr)


def must_git() -> None:
    r = run(["git", "rev-parse", "--is-inside-work-tree"])
    if r.code != 0 or "true" not in r.stdout:
        raise RuntimeError("Not a git repository (git rev-parse failed).")


def safe_strip(s: str) -> str:
    return (s or "").strip()


def try_run(cmd: List[str]) -> str:
    r = run(cmd)
    return safe_strip(r.stdout) if r.code == 0 else ""
