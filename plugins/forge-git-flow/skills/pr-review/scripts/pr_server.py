#!/usr/bin/env python3
"""pr-review 的本機 review 服務：讓 review 頁面可以忽略 AI 意見、寫留言草稿，並把一份 review 送到 Gitea。

設計上的幾條界線：

- **只聽 127.0.0.1**，而且每次啟動產生一把金鑰：頁面要帶著金鑰開啟一次（換成 HttpOnly cookie），
  之後的寫入請求還要帶自訂標頭並通過 Host／Origin 檢查，其他網頁無法代替使用者呼叫。
- **token 不進瀏覽器**：送出 review 由這個服務代為呼叫 Gitea，頁面只知道「有沒有連上」。
- **寫入 Gitea 只發生在使用者按下頁面上的按鈕時**：留言先存成本機的草稿，按「送出」才成為一份 review，
  送出前頁面會列出全部內容；「解決討論／重新開啟」則是按下去就生效，可以隨時改回來。
- 草稿、忽略的意見與「已看」存在 PR 的長期狀態目錄（``review.json``），關掉瀏覽器或換一輪都還在。
"""
from __future__ import annotations

import hmac
import json
import secrets
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import pr_config as cfg
import pr_state as rs
from pr_source import (
    REVIEW_EVENTS,
    PrMetadataError,
    check_repo_access,
    create_review,
    fetch_current_user,
    fetch_pr_metadata,
    fetch_reviews,
    fetch_server_version,
    set_comment_resolved,
    supports_resolve,
    url_origin,
)

AI_LABEL = "_（AI 輔助審查）_"
REVIEW_FILE = "review.json"
SERVER_FILE = "server.json"
SERVICE_NAME = "forge-pr-review"
REMOTE_TTL_SECONDS = 60.0
MAX_REQUEST_BYTES = 1_000_000
MAX_COMMENT_CHARS = 20_000
DEFAULT_IDLE_SECONDS = 12 * 3600

# 頁面上給使用者看的白話說明；完整的技術訊息另外放在「詳細資訊」裡。
PLAIN_REASONS = {
    "login_required": "這台 Gitea 要登入才能讀取資料，貼上 token 就可以了。",
    "token_rejected": "目前存的 token 已經失效（可能被撤銷或過期），請貼上新的。",
    "token_scope": "目前存的 token 權限不夠，請重新產生一個，並勾選下面寫的權限。",
    "token_public_only": "目前存的 token 只能讀公開的專案，請重新產生一個。",
    "no_repo_access": "這個帳號沒有這個專案的讀取權限，請找專案的管理者。",
    "unreachable": "連不上 Gitea，請確認網路或 VPN 之後按「連接」再試一次。",
    "blocked": "請求在到達 Gitea 之前被擋下了。可能需要先連 VPN，或下面的網址不是 Gitea 真正的網址。",
    "redirected": "請求被轉到別的網址了。請確認下面填的是 Gitea 真正的網址。",
    "not_found": "在這台 Gitea 上找不到這個 PR，請確認下面的網址。",
}


def _last_hunk_line(hunk: str) -> Optional[str]:
    """留言當時所在的那一行（``diff_hunk`` 的最後一行，去掉開頭的 ``+``／``-``／空白）。"""
    lines = [line for line in hunk.split("\n") if line and not line.startswith("\\")]
    if not lines:
        return None
    last = lines[-1].rstrip("\r")
    return last[1:] if last[:1] in ("+", "-", " ") else last


class ReviewService:
    """一個 PR 的 review 狀態與對 Gitea 的讀寫。HTTP 層只負責驗證請求，再呼叫這裡的方法。"""

    def __init__(
        self,
        *,
        number: int,
        state_dir: Path,
        page_data: Callable[[], Dict[str, Any]],
        target: Callable[[], Dict[str, Any]],
        render: Callable[[Dict[str, Any]], str],
        remember: Optional[Callable[[Dict[str, Any]], None]] = None,
        project_id: str = "",
    ) -> None:
        """``page_data`` 回傳目前這一輪的頁面資料；``target`` 回傳要連的 Gitea（網址、owner、repo、token）；
        ``render`` 把頁面資料變成 HTML；``remember`` 在讀到 PR 的標題等資訊時被呼叫，讓它們存進長期狀態；
        ``project_id`` 是這個專案在「用過的專案」清單裡的 id，有它頁面才能切換要不要預先分析。"""
        self._remember = remember
        self._project_id = project_id
        self.number = number
        self._state_dir = state_dir
        self._page_data = page_data
        self._target = target
        self._render = render
        self._lock = threading.RLock()
        self._remote_cache: Optional[Dict[str, Any]] = None
        self._remote_at = 0.0
        self._versions: Dict[str, str] = {}

    # ------------------------------------------------------------------ 本機狀態

    def _load(self) -> Dict[str, Any]:
        raw = rs.read_json(self._state_dir / REVIEW_FILE)
        review = raw if isinstance(raw, dict) else {}
        review.setdefault("schema_version", 1)
        for key, empty in (("decisions", {}), ("drafts", []), ("submitted", []), ("viewed", {})):
            if not isinstance(review.get(key), type(empty)):
                review[key] = empty
        return review

    def _save(self, review: Dict[str, Any]) -> None:
        rs.write_json_atomic(self._state_dir / REVIEW_FILE, review)

    @staticmethod
    def _diff_index(data: Dict[str, Any]) -> Dict[Tuple[str, str], Dict[int, str]]:
        """``(路徑, 新舊側) -> {行號: 內容}``，用來確認留言與草稿指到的行還在目前的 diff 裡。"""
        index: Dict[Tuple[str, str], Dict[int, str]] = {}
        for entry in data.get("files") or []:
            new_lines: Dict[int, str] = {}
            old_lines: Dict[int, str] = {}
            for hunk in entry.get("hunks") or []:
                for line in hunk.get("lines") or []:
                    if line.get("new") is not None:
                        new_lines[line["new"]] = line.get("text", "")
                    if line.get("old") is not None:
                        old_lines[line["old"]] = line.get("text", "")
            index[(entry["path"], "new")] = new_lines
            index[(entry["path"], "old")] = old_lines
        return index

    @staticmethod
    def _final_body(draft: Dict[str, Any]) -> str:
        """實際會送到 Gitea 的文字：由 AI 意見而來的留言，結尾加上標示。"""
        body = str(draft.get("body") or "").strip()
        return f"{body}\n\n{AI_LABEL}" if draft.get("finding") else body

    @staticmethod
    def _thread_roots(comments: List[Dict[str, Any]]) -> Dict[Tuple[str, str, Optional[int]], List[Dict[str, Any]]]:
        """``(路徑, 新舊側, 行號) -> 這一行上每一串討論的第一則留言``。Gitea 把「解決了沒」記在第一則留言上。

        同一行上來自不同 review 的留言，在 Gitea 的檔案頁面合成一串、在對話頁面各自成串，
        所以一行上有幾份 review，就有幾則第一則留言；全部都解決了，這一行才算解決。
        """
        grouped: Dict[Tuple[str, str, Optional[int]], Dict[Any, Dict[str, Any]]] = {}
        for item in comments:
            if not isinstance(item.get("id"), int):
                continue
            per_review = grouped.setdefault((item["path"], item["side"], item["line"]), {})
            first = per_review.get(item["review_id"])
            if first is None or item["id"] < first["id"]:
                per_review[item["review_id"]] = item
        return {key: list(per_review.values()) for key, per_review in grouped.items()}

    def _server_version(self, base: str, token: Optional[str]) -> str:
        """這台 Gitea 的版本；讀到一次就記住（服務的存活時間內不會變）。讀不到時回傳空字串。"""
        if base not in self._versions:
            try:
                self._versions[base] = fetch_server_version(base, token)
            except PrMetadataError:
                return ""
        return self._versions[base]

    # ------------------------------------------------------------------ Gitea 的狀態

    def _remote(self, force: bool = False) -> Dict[str, Any]:
        """連線狀態與 PR 上既有的留言；一分鐘內重複詢問時用快取。"""
        with self._lock:
            if not force and self._remote_cache and time.monotonic() - self._remote_at < REMOTE_TTL_SECONDS:
                return self._remote_cache
            try:
                target = self._target()
                problem = ""
            except Exception as exc:  # noqa: BLE001 - 例如 repo 的 remote 被改掉了
                target, problem = {}, str(exc)
            base = target.get("base_url") or ""
            token = target.get("token")
            connection: Dict[str, Any] = {
                "ok": False,
                "host": base,
                "host_guessed": bool(target.get("guessed")),
                "has_token": bool(token),
                "user": "",
                "version": "",
                "can_resolve": None,  # True 可以、False 版本不夠、None 還不知道（沒連上或讀不到版本）
                "message": "",
                "cause": "",
                "token_page": f"{base.rstrip('/')}/user/settings/applications" if base else "",
            }
            info: Dict[str, Any] = {"connection": connection, "comments": [], "reviews": [], "head_sha": ""}
            if not base:
                connection["message"] = problem or "推不出這台 Gitea 的網址。"
            else:
                try:
                    meta = fetch_pr_metadata(base, target["owner"], target["repo"], self.number, token)
                    connection["ok"] = True
                    info["head_sha"] = meta.get("head_sha") or ""
                    if self._remember:
                        self._remember(meta)
                    fetched = fetch_reviews(base, target["owner"], target["repo"], self.number, token)
                    info["comments"], info["reviews"] = fetched["comments"], fetched["reviews"]
                except PrMetadataError as exc:
                    if connection["ok"]:
                        connection["message"] = f"讀不到 PR 上既有的留言：{exc}"
                    else:
                        connection["message"], connection["cause"] = str(exc), exc.cause
                if connection["ok"] and token:
                    try:
                        connection["user"] = fetch_current_user(base, token)
                    except PrMetadataError:
                        connection["user"] = ""
                    connection["version"] = self._server_version(base, token)
                    connection["can_resolve"] = supports_resolve(connection["version"])
            connection["plain"] = (
                "" if connection["ok"] else PLAIN_REASONS.get(connection["cause"], "還讀不到這個 PR 在 Gitea 上的資料。")
            )
            self._remote_cache, self._remote_at = info, time.monotonic()
            return info

    def live(self, force: bool = False) -> Dict[str, Any]:
        """頁面需要的即時狀態：連線、既有留言、草稿、忽略的意見與「已看」。"""
        with self._lock:
            data = self._page_data()
            review = self._load()
            remote = self._remote(force)
            index = self._diff_index(data)
            head = (data.get("round") or {}).get("head_sha") or ""
            user = remote["connection"]["user"]
            own_reviews = {item.get("review_id") for item in review["submitted"]}

            roots = self._thread_roots(remote["comments"])
            comments = []
            for item in remote["comments"]:
                lines = index.get((item["path"], item["side"]))
                anchor = "file"
                if item["line"] and lines and item["line"] in lines:
                    if item["commit_id"] == head or _last_hunk_line(item["diff_hunk"]) == lines[item["line"]]:
                        anchor = "line"
                comments.append(
                    {
                        "id": item["id"], "user": item["user"], "body": item["body"], "path": item["path"],
                        "side": item["side"], "line": item["line"],
                        "resolved": all(
                            root["resolved"] for root in roots.get((item["path"], item["side"], item["line"]), [item])
                        ),
                        "created_at": item["created_at"], "url": item["url"], "anchor": anchor,
                        "in_diff": lines is not None,
                        "mine": bool((user and item["user"] == user) or item["review_id"] in own_reviews),
                    }
                )
            reviews = [
                {**item, "mine": bool((user and item["user"] == user) or item["id"] in own_reviews)}
                for item in remote["reviews"]
                if item["body"].strip() or item["state"] in ("APPROVED", "REQUEST_CHANGES")
            ]
            drafts = []
            for draft in review["drafts"]:
                lines = index.get((draft.get("path") or "", draft.get("side") or "new"))
                valid = draft.get("line") is None or bool(lines and draft["line"] in lines)
                drafts.append({**draft, "valid": valid, "final_body": self._final_body(draft)})
            return {
                "ai_label": AI_LABEL,
                "connection": remote["connection"],
                "head_moved": bool(remote["head_sha"] and head and remote["head_sha"] != head),
                "decisions": review["decisions"],
                "drafts": drafts,
                "comments": comments,
                "reviews": reviews,
                "submitted": review["submitted"][-5:],
                "viewed": review["viewed"],
            }

    def page(self) -> str:
        """目前這一輪的 review 頁面（內含即時狀態）。"""
        data = self._page_data()
        data["live"] = self.live()
        data["theme"] = cfg.load_theme()
        data["hints_seen"] = cfg.load_hints()
        # 排程預先分析時要不要包含這個專案；認不出專案時是 None，頁面就不顯示這個開關
        data["prerun"] = cfg.prerun_enabled(self._project_id) if self._project_id else None
        return self._render(data)

    # ------------------------------------------------------------------ 使用者的操作

    def set_decision(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """忽略一則 AI 意見，或把它復原。"""
        finding_id = str(payload.get("id") or "").strip()
        status = payload.get("status")
        if not finding_id or status not in ("ignored", "open"):
            return {"ok": False, "message": "不認得這個操作。"}
        with self._lock:
            review = self._load()
            if status == "open":
                review["decisions"].pop(finding_id, None)
            else:
                review["decisions"][finding_id] = {
                    "status": "ignored",
                    "title": str(payload.get("title") or "")[:300],
                    "analyzed_at": str(payload.get("analyzed_at") or ""),
                    "at": rs.now_iso(),
                }
            self._save(review)
            return {"ok": True, "live": self.live()}

    def save_draft(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """新增或修改一則留言草稿。``line`` 省略時是整體留言（會併進 review 的說明）。"""
        body = payload.get("body")
        if not isinstance(body, str) or not body.strip():
            return {"ok": False, "message": "留言是空的。"}
        if len(body) > MAX_COMMENT_CHARS:
            return {"ok": False, "message": "留言太長了。"}
        line = payload.get("line")
        if line is not None and (isinstance(line, bool) or not isinstance(line, int) or line <= 0):
            return {"ok": False, "message": "行號不正確。"}
        finding = str(payload.get("finding") or "").strip() or None
        reply_to = payload.get("reply_to")
        if reply_to is not None and (isinstance(reply_to, bool) or not isinstance(reply_to, int)):
            return {"ok": False, "message": "不認得要回覆的留言。"}
        with self._lock:
            review = self._load()
            drafts: List[Dict[str, Any]] = review["drafts"]
            draft_id = str(payload.get("id") or "").strip()
            existing = next((d for d in drafts if d.get("id") == draft_id), None) if draft_id else None
            if existing is None and finding:
                existing = next((d for d in drafts if d.get("finding") == finding), None)
            if existing is not None:
                existing["body"] = body
                existing["updated_at"] = rs.now_iso()
            else:
                used = {d.get("id") for d in drafts}
                number = len(drafts) + 1
                while f"d{number}" in used:
                    number += 1
                drafts.append(
                    {
                        "id": f"d{number}",
                        "path": str(payload.get("path") or ""),
                        "side": "old" if payload.get("side") == "old" else "new",
                        "line": line,
                        "body": body,
                        "finding": finding,
                        "reply_to": reply_to,
                        "created_at": rs.now_iso(),
                    }
                )
            self._save(review)
            return {"ok": True, "live": self.live()}

    def delete_draft(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """刪除一則草稿。"""
        draft_id = str(payload.get("id") or "")
        with self._lock:
            review = self._load()
            review["drafts"] = [d for d in review["drafts"] if d.get("id") != draft_id]
            self._save(review)
            return {"ok": True, "live": self.live()}

    def set_viewed(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """記住某個檔案看過了（以檔案簽章為準，內容變了就自動失效）。"""
        path = str(payload.get("path") or "")
        signature = payload.get("signature")
        if not path:
            return {"ok": False, "message": "沒有指定檔案。"}
        with self._lock:
            review = self._load()
            if isinstance(signature, str) and signature:
                review["viewed"][path] = signature
            else:
                review["viewed"].pop(path, None)
            self._save(review)
            return {"ok": True}

    def set_theme(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """記住頁面的主題。它是這台電腦的偏好，不屬於某一個 PR，所以存在設定資料夾。"""
        theme = payload.get("theme")
        if not isinstance(theme, str) or theme not in cfg.THEMES:
            return {"ok": False, "message": "不認得這個主題。"}
        with self._lock:
            if not cfg.save_theme(theme):
                return {"ok": False, "message": "主題沒有存起來。"}
            return {"ok": True, "theme": theme}

    def dismiss_hint(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """記住使用者已經看過某個一次性的提示（按了「知道了」），之後不再顯示。"""
        hint = payload.get("id")
        with self._lock:
            if not isinstance(hint, str) or not cfg.save_hint(hint):
                return {"ok": False, "message": "不認得這個提示。"}
            return {"ok": True, "hints_seen": cfg.load_hints()}

    def set_prerun(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """開或關「排程預先分析這個專案」。它是這台電腦對這個專案的設定，不屬於某一個 PR。"""
        enabled = payload.get("enabled")
        with self._lock:
            if not isinstance(enabled, bool) or not self._project_id:
                return {"ok": False, "message": "設定沒有存起來。"}
            if not cfg.set_prerun(self._project_id, enabled):
                return {"ok": False, "message": "設定沒有存起來。"}
            return {"ok": True, "prerun": enabled}

    def connect(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """存入這台 Gitea 的 token。先確認它讀得到這個 repo，確認不了就不存。"""
        target = self._target()
        base = cfg.normalize_host_url(str(payload.get("url") or target.get("base_url") or ""))
        token = str(payload.get("token") or "").strip()
        if not base:
            return {"ok": False, "message": "Gitea 的網址不正確。"}
        if not token:
            return {"ok": False, "message": "沒有貼上 token。"}
        try:
            check_repo_access(base, target["owner"], target["repo"], token)
        except PrMetadataError as exc:
            return {"ok": False, "message": f"這個 token 沒有儲存。{exc}"}
        config = cfg.load_config()
        if not cfg.write_token(config, base, token) or cfg.read_token(config, base) != token:
            return {"ok": False, "message": f"寫入 {cfg.store_label(config)} 失敗，token 沒有儲存。"}
        entry = config["hosts"].setdefault(base, {"ssh_hosts": []})
        origin = url_origin(base)
        remote_host = target.get("remote_host") or ""
        if target.get("ssh") and origin and remote_host and remote_host != origin[1]:
            entry["ssh_hosts"] = sorted(set(entry.get("ssh_hosts") or []) | {remote_host})
        cfg.save_config(config)
        return {"ok": True, "live": self.live(force=True)}

    def resolve(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """把一行上的討論標成已解決，或重新開啟。使用者在頁面上按下時立刻對 Gitea 生效，可以再改回來。

        ``id`` 是那一行上任何一則留言；實際要改的是那一行上每一串討論的第一則留言（見 ``_thread_roots``）。
        """
        resolved = payload.get("resolved")
        comment_id = payload.get("id")
        if not isinstance(resolved, bool) or isinstance(comment_id, bool) or not isinstance(comment_id, int):
            return {"ok": False, "message": "不認得這個操作。"}
        with self._lock:
            target = self._target()
            token, base = target.get("token"), target.get("base_url")
            if not base or not token:
                return {"ok": False, "message": "還沒有連接 Gitea，沒辦法解決討論。"}
            comments = self._remote()["comments"]
            anchor = next((item for item in comments if item["id"] == comment_id), None)
            if anchor is None:
                # 只處理這個 PR 上看得到的留言，不讓頁面指定任意的留言編號
                return {"ok": False, "message": "找不到這則留言，請按「重新讀取」之後再試一次。"}
            try:
                for root in self._thread_roots(comments)[(anchor["path"], anchor["side"], anchor["line"])]:
                    set_comment_resolved(base, target["owner"], target["repo"], root["id"], token, resolved)
            except PrMetadataError as exc:
                return {"ok": False, "message": f"沒有完成。{exc}", "live": self.live(force=True)}
            return {"ok": True, "live": self.live(force=True)}

    def refresh(self, _payload: Dict[str, Any]) -> Dict[str, Any]:
        """重新向 Gitea 讀取連線狀態與既有的留言。"""
        return {"ok": True, "live": self.live(force=True)}

    def submit(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """把草稿送成一份 review。只有使用者在頁面上按下送出時才會被呼叫。"""
        event = payload.get("event")
        if event not in REVIEW_EVENTS:
            return {"ok": False, "message": "請選擇這份 review 的類型。"}
        summary = str(payload.get("body") or "").strip()
        with self._lock:
            target = self._target()
            token = target.get("token")
            base = target.get("base_url")
            if not base or not token:
                return {"ok": False, "message": "還沒有連接 Gitea，沒辦法送出。"}
            data = self._page_data()
            review = self._load()
            index = self._diff_index(data)
            head = (data.get("round") or {}).get("head_sha") or ""

            inline: List[Dict[str, Any]] = []
            general: List[str] = []
            sent: List[Dict[str, Any]] = []
            kept = 0
            for draft in review["drafts"]:
                text = self._final_body(draft)
                if draft.get("line") is None:
                    prefix = f"`{draft['path']}`：" if draft.get("path") else ""
                    general.append(prefix + text)
                    sent.append(draft)
                    continue
                lines = index.get((draft.get("path") or "", draft.get("side") or "new"))
                if lines and draft["line"] in lines:
                    inline.append({"path": draft["path"], "side": draft.get("side") or "new", "line": draft["line"], "body": text})
                    sent.append(draft)
                else:
                    kept += 1
            body = "\n\n".join(part for part in [summary, *general] if part)
            if event == "COMMENT" and not inline and not body:
                return {"ok": False, "message": "沒有可以送出的內容。"}
            if event == "REQUEST_CHANGES" and not body.strip():
                # Gitea 規定「要求修改」一定要有說明（只有行內留言不夠），先在這裡擋下，不讓使用者看到 422
                return {
                    "ok": False, "need_body": True,
                    "message": "「要求修改」要寫一段整體說明，Gitea 才會接受。請在「整體說明」寫下要作者修改什麼。",
                }

            if not payload.get("force"):
                try:
                    meta = fetch_pr_metadata(base, target["owner"], target["repo"], self.number, token)
                    if meta.get("head_sha") and head and meta["head_sha"] != head:
                        return {
                            "ok": False,
                            "head_moved": True,
                            "message": "作者在你 review 的期間推了新的 commit。現在送出，留言會掛在你看的那一版上，"
                            "在 Gitea 可能被標成過時。建議先回到對話重新 review 一次；要照樣送出，請再按一次送出。",
                        }
                except PrMetadataError:
                    pass
            try:
                result = create_review(base, target["owner"], target["repo"], self.number, token, event, body, head, inline)
            except PrMetadataError as exc:
                return {"ok": False, "message": f"沒有送出。{exc}"}

            sent_ids = {draft["id"] for draft in sent}
            review["drafts"] = [d for d in review["drafts"] if d.get("id") not in sent_ids]
            titles = {f.get("id"): f.get("title") or "" for f in ((data.get("analysis") or {}).get("findings") or [])}
            analyzed_at = (data.get("round") or {}).get("analyzed_at") or ""
            for draft in sent:
                if draft.get("finding"):
                    review["decisions"][draft["finding"]] = {
                        "status": "sent", "title": titles.get(draft["finding"], ""),
                        "analyzed_at": analyzed_at, "at": rs.now_iso(),
                    }
            review["submitted"].append(
                {
                    "at": rs.now_iso(), "round": (data.get("round") or {}).get("number"), "event": event,
                    "review_id": result["id"], "url": result["url"], "comments": len(inline), "head_sha": head,
                }
            )
            self._save(review)
            return {
                "ok": True, "url": result["url"], "event": event, "sent": len(inline), "kept": kept,
                "live": self.live(force=True),
            }


# --------------------------------------------------------------------------- HTTP 層


def make_server(
    service: ReviewService, port: int = 0, idle_seconds: float = DEFAULT_IDLE_SECONDS, code: str = ""
) -> Tuple[ThreadingHTTPServer, str]:
    """建立只聽 127.0.0.1 的 HTTP 服務，回傳 ``(server, 金鑰)``。閒置超過 ``idle_seconds`` 會自己關掉。

    ``code`` 是這個行程載入的程式的指紋，由 ``/api/ping`` 回報，讓 ``serve`` 分辨執行中的服務是不是舊版。
    """
    key = secrets.token_urlsafe(24)
    actions: Dict[str, Callable[[Dict[str, Any]], Dict[str, Any]]] = {
        "/api/decision": service.set_decision,
        "/api/draft": service.save_draft,
        "/api/draft/delete": service.delete_draft,
        "/api/viewed": service.set_viewed,
        "/api/theme": service.set_theme,
        "/api/hint": service.dismiss_hint,
        "/api/prerun": service.set_prerun,
        "/api/connect": service.connect,
        "/api/resolve": service.resolve,
        "/api/refresh": service.refresh,
        "/api/submit": service.submit,
    }

    class Handler(BaseHTTPRequestHandler):
        server_version = SERVICE_NAME
        protocol_version = "HTTP/1.1"

        def log_message(self, *args: Any) -> None:  # noqa: D401 - 不輸出存取紀錄
            """Silence request logging."""

        # -- 驗證
        def _port(self) -> int:
            return self.server.server_address[1]

        def _host_ok(self) -> bool:
            return self.headers.get("Host", "") in (f"127.0.0.1:{self._port()}", f"localhost:{self._port()}")

        def _origin_ok(self) -> bool:
            origin = self.headers.get("Origin")
            return origin is None or origin in (f"http://127.0.0.1:{self._port()}", f"http://localhost:{self._port()}")

        def _cookie_name(self) -> str:
            return f"forge_pr_{self._port()}"

        def _authed(self) -> bool:
            for part in self.headers.get("Cookie", "").split(";"):
                name, _, value = part.strip().partition("=")
                if name == self._cookie_name() and hmac.compare_digest(value, key):
                    return True
            return False

        # -- 回應
        def _send(self, status: int, body: bytes, content_type: str, extra: Optional[Dict[str, str]] = None) -> None:
            self.server.last_seen = time.monotonic()  # type: ignore[attr-defined]
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            for name, value in (extra or {}).items():
                self.send_header(name, value)
            self.end_headers()
            self.wfile.write(body)

        def _json(self, status: int, payload: Dict[str, Any]) -> None:
            self._send(status, json.dumps(payload, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

        def _text(self, status: int, message: str) -> None:
            self._send(status, message.encode("utf-8"), "text/plain; charset=utf-8")

        # -- 路由
        def do_GET(self) -> None:  # noqa: N802
            if not self._host_ok():
                self._text(403, "拒絕存取。")
                return
            parsed = urllib.parse.urlsplit(self.path)
            if parsed.path == "/api/ping":
                self._json(200, {"ok": True, "service": SERVICE_NAME, "pr": service.number, "code": code})
                return
            if parsed.path in ("/", "/index.html"):
                given = urllib.parse.parse_qs(parsed.query).get("k", [""])[0]
                if given:
                    if not hmac.compare_digest(given, key):
                        self._text(403, "這個連結已經失效，請回到對話重新開啟 review 頁面。")
                        return
                    # 用 Lax 不用 Strict：Safari 把休眠的分頁叫回來時是「從歷史紀錄載入」，這種載入不送 Strict 的 cookie
                    # （WebKit bug 232666），頁面就會被當成沒登入。Lax 只跟著頂層的 GET 導覽送出；會改東西的請求都是 POST，
                    # 另外有 Origin 與 X-Forge-Request 兩道檢查，所以跨站偽造的請求仍然進不來。
                    cookie = f"{self._cookie_name()}={key}; HttpOnly; SameSite=Lax; Path=/"
                    self._send(302, b"", "text/plain; charset=utf-8", {"Location": "/", "Set-Cookie": cookie})
                    return
                if not self._authed():
                    self._text(403, "請回到對話重新開啟 review 頁面（這個頁面要從對話給的連結進入）。")
                    return
                try:
                    self._send(200, service.page().encode("utf-8"), "text/html; charset=utf-8")
                except Exception as exc:  # noqa: BLE001 - 把原因顯示在頁面上
                    self._text(500, f"頁面產生失敗：{exc}")
                return
            if parsed.path == "/api/live":
                # Lax 的 cookie 會跟著別的網站發起的頂層導覽送來，所以讀資料的 GET 也要有頁面才會加的自訂標頭
                if not (self._authed() and self.headers.get("X-Forge-Request") == "1"):
                    self._json(403, {"ok": False, "message": "拒絕存取。"})
                    return
                self._json(200, {"ok": True, "live": service.live()})
                return
            self._text(404, "找不到。")

        def do_POST(self) -> None:  # noqa: N802
            parsed = urllib.parse.urlsplit(self.path)
            action = actions.get(parsed.path)
            if not (self._host_ok() and self._origin_ok() and self._authed()) or self.headers.get("X-Forge-Request") != "1":
                self._json(403, {"ok": False, "message": "拒絕存取。"})
                return
            if action is None:
                self._json(404, {"ok": False, "message": "找不到。"})
                return
            try:
                length = int(self.headers.get("Content-Length") or 0)
                if length > MAX_REQUEST_BYTES:
                    self._json(413, {"ok": False, "message": "內容太大。"})
                    return
                payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
                if not isinstance(payload, dict):
                    raise ValueError("payload must be an object")
            except (ValueError, UnicodeDecodeError):
                self._json(400, {"ok": False, "message": "請求的格式不正確。"})
                return
            try:
                self._json(200, action(payload))
            except Exception as exc:  # noqa: BLE001 - 把原因回給頁面，服務本身繼續運作
                self._json(500, {"ok": False, "message": f"發生錯誤：{exc}"})

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    server.daemon_threads = True
    server.last_seen = time.monotonic()  # type: ignore[attr-defined]

    def watchdog() -> None:
        while True:
            time.sleep(min(30.0, max(0.2, idle_seconds / 4)))
            if time.monotonic() - server.last_seen > idle_seconds:  # type: ignore[attr-defined]
                server.shutdown()
                return

    threading.Thread(target=watchdog, daemon=True).start()
    return server, key
