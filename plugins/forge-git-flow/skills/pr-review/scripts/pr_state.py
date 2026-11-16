#!/usr/bin/env python3
"""pr-review 的長期狀態：每個 PR 一份、按「輪」記錄。

狀態放在 XDG data 目錄（預設 ``~/.local/share/claude-forge/pr-review/``），
不放在 repo 的 ``.ai-artifacts/`` 裡：後者依專案的 Cache 化原則必須可以隨時 ``rm -rf``，
而「上一輪看到哪個 commit、當時的分析結果」刪掉就接不回去了。

目錄結構::

    <data-root>/<project-key>/pr-<N>/
      state.json                 # PR 基本資料與各輪紀錄
      rounds/r<k>/analysis.json  # 該輪驗證過的分析結果

每一輪綁一個 head commit。``file_signatures`` 記下當輪每個檔案的 diff 簽章，
下一輪用它判斷哪些檔案有新變更。
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

STATE_SCHEMA_VERSION = 1


def data_root() -> Path:
    """回傳 pr-review 的資料根目錄（可用 ``XDG_DATA_HOME`` 覆寫）。"""
    base = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    return Path(base) / "claude-forge" / "pr-review"


def project_key(host: str, owner: str, repo: str) -> str:
    """以「主機/owner/repo」產生專案鍵：repo 名稱加 SHA-256 前 12 碼。"""
    identity = f"{host}/{owner}/{repo}".lower()
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:12]
    slug = re.sub(r"[^a-z0-9._-]+", "-", repo.lower()).strip("-") or "repo"
    return f"{slug}-{digest}"


def pr_state_dir(key: str, number: int) -> Path:
    """回傳單一 PR 的狀態目錄。"""
    return data_root() / key / f"pr-{int(number)}"


def now_iso() -> str:
    """回傳 UTC 的 ISO 8601 時間字串。"""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def read_json(path: Path) -> Optional[Any]:
    """讀 JSON 檔；不存在或格式壞掉時回傳 ``None``。"""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None


def write_json_atomic(path: Path, obj: Any) -> None:
    """先寫暫存檔再改名，避免寫到一半被中斷而留下壞掉的狀態檔。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(obj, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        os.replace(tmp_name, path)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def load_state(state_dir: Path) -> Dict[str, Any]:
    """讀取 PR 的狀態；沒有時回傳空的初始狀態。"""
    state = read_json(state_dir / "state.json")
    if isinstance(state, dict) and state.get("schema_version") == STATE_SCHEMA_VERSION:
        state.setdefault("rounds", [])
        return state
    return {"schema_version": STATE_SCHEMA_VERSION, "rounds": []}


def save_state(state_dir: Path, state: Dict[str, Any]) -> None:
    """寫回 PR 的狀態。"""
    state["updated_at"] = now_iso()
    write_json_atomic(state_dir / "state.json", state)


def latest_round(state: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """回傳最新一輪的紀錄。"""
    rounds: List[Dict[str, Any]] = state.get("rounds") or []
    return rounds[-1] if rounds else None


def find_round(state: Dict[str, Any], number: int) -> Optional[Dict[str, Any]]:
    """依輪次編號找紀錄。"""
    for record in state.get("rounds") or []:
        if record.get("round") == number:
            return record
    return None


def round_analysis_path(state_dir: Path, number: int) -> Path:
    """回傳某一輪「驗證過的分析結果」的存放路徑。"""
    return state_dir / "rounds" / f"r{int(number)}" / "analysis.json"


def compute_rules_hash(rule_files: List[Path]) -> str:
    """對會影響 review 結果的規則檔做 SHA-256；缺少的檔案直接略過。"""
    digest = hashlib.sha256()
    for path in rule_files:
        if path.exists():
            digest.update(path.name.encode("utf-8"))
            digest.update(b"\n")
            digest.update(path.read_bytes())
            digest.update(b"\n---\n")
    return digest.hexdigest()


def compare_signatures(
    previous: Optional[Dict[str, str]], current: Dict[str, str]
) -> Dict[str, Any]:
    """比較上一輪與這一輪的檔案簽章。

    回傳 ``per_file``（每個檔案是 ``new``／``changed``／``unchanged``）與
    ``dropped``（上一輪有、這一輪已不在 diff 裡的檔案）。沒有上一輪時 ``per_file`` 為空。
    """
    if not previous:
        return {"per_file": {}, "dropped": []}
    per_file: Dict[str, str] = {}
    for path, signature in current.items():
        if path not in previous:
            per_file[path] = "new"
        elif previous[path] != signature:
            per_file[path] = "changed"
        else:
            per_file[path] = "unchanged"
    dropped = sorted(path for path in previous if path not in current)
    return {"per_file": per_file, "dropped": dropped}
