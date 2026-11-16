#!/usr/bin/env python3
"""CLI wrapper around :func:`utils.resolve_branch_base`.

Prints the resolved branch-base info as JSON to stdout. Consumed by shell-based
branch-diff skills (branch-diff-annotator, branch-diff-unit-test, branch-wrap-up).
Python-based skills should ``from utils import resolve_branch_base`` instead.

Output schema: { mode, current_branch, head, base_ref, base_commit, range, notes }.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(THIS_DIR))

from utils import resolve_branch_base

if __name__ == "__main__":
    print(json.dumps(resolve_branch_base(), ensure_ascii=False, indent=2))
