#!/usr/bin/env python3
"""pr-review 的機器本地設定與 token 存放。

設定檔（不含祕密）在 ``${XDG_DATA_HOME:-~/.local/share}/claude-forge/pr-review/config.json``::

    {
      "version": 1,
      "hosts": {
        "https://gitea.example.com": { "ssh_hosts": ["git.example.com"] }
      }
    }

``hosts`` 列出「哪幾台 Gitea 有存 token」，以及 git remote 是 SSH 時、SSH 主機對應到哪個網址。
token 本身不寫在設定檔裡，由 secret store 保存，後端依平台選擇（與 feature-spec-builder 的做法一致）：

- macOS：鑰匙圈（``security`` CLI），service 為 :data:`KEYCHAIN_SERVICE`，account 是 Gitea 的網址
- 其他平台：設定檔旁邊、權限 0600 的 ``secrets.json``

設定檔可以用 ``"secret_store": "file"`` 或 ``"keychain"`` 指定後端。

同一個資料夾另有 ``preferences.json``，存 review 頁面的介面偏好（主題、看過的提示）與排程預先分析的設定（範圍、新專案的預設），
以及 ``projects.json``，記下在哪些專案資料夾用過 pr-review、各自要不要讓排程預先分析。
專案資料夾的路徑因機器而異，所以只存在這裡，不寫進任何 repo。

token 以「Gitea 的網址」為 key 存放，所以它天生綁定主機：呼叫端只在 API 的來源與那個網址相同時才把它取出來。
相較於環境變數，它也不會被這台機器上其他從 shell 啟動的程式讀到。
"""
from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
import sys
import urllib.parse
from pathlib import Path
from typing import Any, Dict, List, Optional

CONFIG_VERSION = 1
KEYCHAIN_SERVICE = "com.claude.forge-pr-review"
THEMES = ("auto", "light", "dark")
# 頁面上只出現一次的提示；使用者按「知道了」之後記在這台電腦上
HINTS = ("line-comment",)
# 排程預先分析的範圍：mine 只跑請我 review 的與我 review 過的；all 再加上其他人開的所有 PR
PRERUN_SCOPES = ("mine", "all")


def config_dir() -> Path:
    """設定檔所在的資料夾（與 pr-review 的長期狀態同一個根目錄）。"""
    xdg = os.environ.get("XDG_DATA_HOME")
    base = Path(xdg) if xdg else Path.home() / ".local" / "share"
    return base / "claude-forge" / "pr-review"


def config_path() -> Path:
    """設定檔的路徑。"""
    return config_dir() / "config.json"


def secrets_path() -> Path:
    """檔案後端存放 token 的路徑。"""
    return config_dir() / "secrets.json"


def normalize_host_url(url: str) -> Optional[str]:
    """把 Gitea 的網址整理成固定的寫法（主機小寫、去掉結尾的斜線）；不是 http(s) 網址時回傳 ``None``。"""
    try:
        parsed = urllib.parse.urlsplit(url.strip())
        port = parsed.port
    except ValueError:
        return None
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return None
    netloc = parsed.hostname.lower()
    if port:
        netloc = f"{netloc}:{port}"
    return f"{parsed.scheme}://{netloc}{parsed.path.rstrip('/')}"


def load_config() -> Dict[str, Any]:
    """讀取設定檔；不存在或格式不對時回傳空的設定。"""
    config: Dict[str, Any] = {"version": CONFIG_VERSION, "hosts": {}}
    try:
        raw = json.loads(config_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return config
    if not isinstance(raw, dict):
        return config
    if raw.get("secret_store") in ("keychain", "file"):
        config["secret_store"] = raw["secret_store"]
    hosts = raw.get("hosts")
    if isinstance(hosts, dict):
        for url, entry in hosts.items():
            normalized = normalize_host_url(url) if isinstance(url, str) else None
            if not normalized:
                continue
            aliases = entry.get("ssh_hosts") if isinstance(entry, dict) else None
            config["hosts"][normalized] = {
                "ssh_hosts": sorted(
                    {alias.strip().lower() for alias in aliases or [] if isinstance(alias, str) and alias.strip()}
                )
            }
    return config


def write_private(path: Path, text: str) -> None:
    """以只有自己可讀寫的權限寫檔（資料夾 0700、檔案 0600），並以改名的方式原子替換。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(path.parent, 0o700)
    except OSError:
        pass
    temp = path.with_name(path.name + ".tmp")
    fd = os.open(str(temp), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(text)
    os.chmod(temp, 0o600)
    os.replace(temp, path)


_write_private = write_private


def save_config(config: Dict[str, Any]) -> None:
    """寫回設定檔。"""
    payload: Dict[str, Any] = {"version": CONFIG_VERSION, "hosts": config.get("hosts") or {}}
    if config.get("secret_store"):
        payload["secret_store"] = config["secret_store"]
    _write_private(config_path(), json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def preferences_path() -> Path:
    """介面偏好的路徑。與設定檔分開存：改偏好不會重寫記錄 Gitea 主機的那個檔。"""
    return config_dir() / "preferences.json"


def _load_preferences() -> Dict[str, Any]:
    try:
        raw = json.loads(preferences_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return raw if isinstance(raw, dict) else {}


def load_theme() -> str:
    """review 頁面的主題：``"auto"``（跟隨系統）、``"light"`` 或 ``"dark"``；沒存過或內容不認得時是 ``"auto"``。

    存在這裡而不是瀏覽器裡，是因為 review 服務每次啟動的 port 不同，瀏覽器會把它當成另一個網站。
    """
    theme = _load_preferences().get("theme")
    return theme if theme in THEMES else "auto"


def save_theme(theme: str) -> bool:
    """記住 review 頁面的主題；不認得的值或寫不進去時回傳 ``False``。"""
    if theme not in THEMES:
        return False
    preferences = _load_preferences()
    preferences["theme"] = theme
    try:
        write_private(preferences_path(), json.dumps(preferences, ensure_ascii=False, indent=2) + "\n")
    except OSError:
        return False
    return True


def load_hints() -> List[str]:
    """使用者已經按過「知道了」的提示。和主題一樣存在這裡：服務每次啟動的 port 不同，瀏覽器記不住。"""
    seen = _load_preferences().get("hints_seen")
    return [hint for hint in HINTS if isinstance(seen, list) and hint in seen]


def save_hint(hint: str) -> bool:
    """記住某個提示已經看過；不認得的名稱或寫不進去時回傳 ``False``。"""
    if hint not in HINTS:
        return False
    preferences = _load_preferences()
    preferences["hints_seen"] = sorted(set(load_hints()) | {hint})
    try:
        write_private(preferences_path(), json.dumps(preferences, ensure_ascii=False, indent=2) + "\n")
    except OSError:
        return False
    return True


def load_prerun_settings() -> Dict[str, Any]:
    """排程預先分析的設定；沒存過或內容不認得的欄位用預設值。

    - ``scope``：``"mine"``（預設）只跑請我 review 的與我 review 過的 PR；``"all"`` 再加上其他人開的所有 PR
    - ``new_projects``：新記下的專案要不要預先分析（預設要）

    幾點跑、星期幾跑不在這裡：那是排程自己的屬性，只存在排程裡，免得兩邊寫的不一樣。
    """
    raw = _load_preferences().get("prerun")
    saved = raw if isinstance(raw, dict) else {}
    return {
        "scope": saved.get("scope") if saved.get("scope") in PRERUN_SCOPES else "mine",
        "new_projects": saved.get("new_projects") is not False,
    }


def save_prerun_settings(scope: Optional[str] = None, new_projects: Optional[bool] = None) -> bool:
    """修改排程預先分析的設定，``None`` 的欄位不動；不認得的範圍或寫不進去時回傳 ``False``。"""
    if scope is not None and scope not in PRERUN_SCOPES:
        return False
    settings = load_prerun_settings()
    if scope is not None:
        settings["scope"] = scope
    if new_projects is not None:
        settings["new_projects"] = bool(new_projects)
    preferences = _load_preferences()
    preferences["prerun"] = settings
    try:
        write_private(preferences_path(), json.dumps(preferences, ensure_ascii=False, indent=2) + "\n")
    except OSError:
        return False
    return True


def projects_path() -> Path:
    """「用過的專案」清單的路徑。"""
    return config_dir() / "projects.json"


def load_projects() -> List[Dict[str, Any]]:
    """用過 pr-review 的專案，照記下的先後排列；檔案不存在或格式不對時是空的。

    每一項有 ``id``（同一個 repo 的每個 worktree 都一樣）、``path``（最近一次使用的資料夾）、
    ``prerun``（排程預先分析時要不要包含它）與 ``added_at``。
    """
    try:
        raw = json.loads(projects_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    items = raw.get("projects") if isinstance(raw, dict) else None
    projects: List[Dict[str, Any]] = []
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict):
            continue
        project_id, path = item.get("id"), item.get("path")
        if not (isinstance(project_id, str) and project_id and isinstance(path, str) and path):
            continue
        added_at = item.get("added_at")
        projects.append(
            {
                "id": project_id, "path": path,
                # 只有明確寫成 false 才是關掉：沒有這一欄的舊資料視為開著
                "prerun": item.get("prerun") is not False,
                "added_at": added_at if isinstance(added_at, str) else "",
            }
        )
    return projects


def _save_projects(projects: List[Dict[str, Any]]) -> bool:
    try:
        write_private(
            projects_path(), json.dumps({"version": 1, "projects": projects}, ensure_ascii=False, indent=2) + "\n"
        )
    except OSError:
        return False
    return True


def remember_project(project_id: str, path: str, now: str) -> bool:
    """記住一個用過的專案，回傳清單有沒有被改寫。

    新記下的專案要不要預先分析，照 :func:`load_prerun_settings` 的 ``new_projects``（預設要，使用者可以再個別開關）。
    已經記過的只在資料夾換了位置時更新，不會動使用者設定的開關。
    """
    projects = load_projects()
    for project in projects:
        if project["id"] == project_id:
            if project["path"] == path:
                return False
            project["path"] = path
            return _save_projects(projects)
    projects.append(
        {"id": project_id, "path": path, "prerun": load_prerun_settings()["new_projects"], "added_at": now}
    )
    return _save_projects(projects)


def prerun_enabled(project_id: str) -> Optional[bool]:
    """排程預先分析時要不要包含這個專案；還沒記過這個專案時回傳 ``None``。"""
    for project in load_projects():
        if project["id"] == project_id:
            return bool(project["prerun"])
    return None


def set_prerun(project_id: str, enabled: bool) -> bool:
    """開或關某個專案的預先分析；沒記過這個專案、或寫不進去時回傳 ``False``。"""
    projects = load_projects()
    for project in projects:
        if project["id"] == project_id:
            project["prerun"] = bool(enabled)
            return _save_projects(projects)
    return False


def host_for_origin(config: Dict[str, Any], origin: Optional[tuple]) -> Optional[str]:
    """找出設定檔裡來源（scheme、主機、port）與 ``origin`` 相同的那一台。"""
    if origin is None:
        return None
    for url in config.get("hosts") or {}:
        if _origin(url) == origin:
            return url
    return None


def host_for_ssh(config: Dict[str, Any], ssh_host: str) -> Optional[str]:
    """git remote 是 SSH 時，找出這個 SSH 主機對應的 Gitea 網址。"""
    wanted = ssh_host.lower()
    for url, entry in (config.get("hosts") or {}).items():
        origin = _origin(url)
        if (origin and origin[1] == wanted) or wanted in (entry.get("ssh_hosts") or []):
            return url
    return None


def _origin(url: str) -> Optional[tuple]:
    try:
        parsed = urllib.parse.urlsplit(url)
        port = parsed.port
    except ValueError:
        return None
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return None
    return (parsed.scheme, parsed.hostname.lower(), port or (443 if parsed.scheme == "https" else 80))


# --------------------------------------------------------------------------- secret store


def backend(config: Dict[str, Any]) -> str:
    """回傳 ``"keychain"`` 或 ``"file"``。"""
    chosen = config.get("secret_store")
    if chosen in ("keychain", "file"):
        return chosen
    return "keychain" if sys.platform == "darwin" and shutil.which("security") else "file"


def store_label(config: Dict[str, Any]) -> str:
    """給使用者看的 secret store 名稱。"""
    return "macOS 鑰匙圈" if backend(config) == "keychain" else f"{secrets_path()}（權限 0600）"


def _security(args: List[str]) -> "subprocess.CompletedProcess[str]":
    try:
        return subprocess.run(["security", *args], capture_output=True, text=True, check=False)
    except OSError:
        return subprocess.CompletedProcess(args, returncode=1, stdout="", stderr="")


def _secrets_load() -> Dict[str, str]:
    try:
        data = json.loads(secrets_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return {k: v for k, v in data.items() if isinstance(k, str) and isinstance(v, str)} if isinstance(data, dict) else {}


def secret_store_problem(config: Dict[str, Any]) -> Optional[str]:
    """secret store 目前不能安全使用時，回傳要告訴使用者的原因。"""
    if backend(config) != "file" or os.name != "posix":
        return None
    path = secrets_path()
    try:
        mode = stat.S_IMODE(path.stat().st_mode)
    except OSError:
        return None
    if mode & 0o077:
        return f"{path} 的權限太寬（其他使用者也讀得到），沒有使用裡面的 token；請執行 chmod 600 \"{path}\"。"
    return None


def read_token(config: Dict[str, Any], url: str) -> Optional[str]:
    """讀出某一台 Gitea 的 token；沒有、或存放的檔案權限不安全時回傳 ``None``。"""
    if backend(config) == "keychain":
        result = _security(["find-generic-password", "-s", KEYCHAIN_SERVICE, "-a", url, "-w"])
        return (result.stdout.strip() or None) if result.returncode == 0 else None
    if secret_store_problem(config):
        return None
    return _secrets_load().get(url) or None


def write_token(config: Dict[str, Any], url: str, token: str) -> bool:
    """存入（覆蓋）某一台 Gitea 的 token。

    鑰匙圈後端沿用 feature-spec-builder 的寫法：``security add-generic-password -w`` 只能從參數接收內容，
    寫入的瞬間 token 會出現在行程列表裡，這是 Apple 工具的限制。
    """
    if backend(config) == "keychain":
        _security(["delete-generic-password", "-s", KEYCHAIN_SERVICE, "-a", url])
        result = _security(
            ["add-generic-password", "-s", KEYCHAIN_SERVICE, "-a", url, "-l", f"forge pr-review: {url}", "-w", token]
        )
        return result.returncode == 0
    data = _secrets_load()
    data[url] = token
    try:
        _write_private(secrets_path(), json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    except OSError:
        return False
    return True


def delete_token(config: Dict[str, Any], url: str) -> bool:
    """刪除某一台 Gitea 的 token；原本就沒有時回傳 ``False``。"""
    if backend(config) == "keychain":
        return _security(["delete-generic-password", "-s", KEYCHAIN_SERVICE, "-a", url]).returncode == 0
    data = _secrets_load()
    if url not in data:
        return False
    del data[url]
    try:
        if data:
            _write_private(secrets_path(), json.dumps(data, ensure_ascii=False, indent=2) + "\n")
        else:
            secrets_path().unlink()
    except OSError:
        return False
    return True
