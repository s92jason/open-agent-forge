#!/usr/bin/env python3
"""PR 來源解析：PR 參照、git remote URL，以及 Gitea 的 PR metadata。

這個模組不碰 git 也不寫檔，只負責三件事：

- 把使用者給的「PR 編號或網址」解析成 :class:`PrRef`
- 把 git remote URL 解析成 :class:`RemoteInfo`（會剝掉 URL 內嵌的帳密）
- 向 Gitea API 讀取 PR 的標題、目標分支等 metadata（唯讀，可省略）

Token 一定要綁定主機：只有當 API 的來源（scheme、主機、port）與「存這個 token 時指定的 Gitea 網址」
完全相同時才會送出。token 的來源有兩種：用 ``set-token`` 存進 secret store 的（以網址為 key，見 ``pr_config.py``），
以及環境變數 ``GITEA_TOKEN``（必須搭配 ``GITEA_BASE_URL`` 宣告它屬於哪一台）。
remote 與貼上的 PR 網址都是輸入，不能由輸入決定憑證要送去哪裡；轉址到不同來源時也一律拒絕。
"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

USER_AGENT = "forge-pr-review"

_PR_PATH_RE = re.compile(
    r"^(?P<prefix>(?:/[^/]+)*?)/(?P<owner>[^/]+)/(?P<repo>[^/]+)/pulls?/(?P<num>\d+)(?:/.*)?$"
)
_SCP_LIKE_RE = re.compile(r"^(?:[^@/]+@)?(?P<host>[^:/]+):(?P<path>[^/].*)$")


class PrSourceError(Exception):
    """PR 參照或 remote 無法解析。"""


class PrMetadataError(Exception):
    """讀取 PR metadata 失敗（網路、權限或回應格式）。

    ``cause`` 是機器可讀的原因代碼（見 :func:`explain_http_error`）；``server_message`` 是伺服器在
    錯誤回應裡附的說明（已截短並壓成單行，屬於外部資料）。
    """

    def __init__(
        self, message: str, *, status: Optional[int] = None, cause: str = "", server_message: str = ""
    ) -> None:
        super().__init__(message)
        self.status = status
        self.cause = cause
        self.server_message = server_message


@dataclass
class PrRef:
    """使用者指定的 PR。只給編號時，主機與 repo 由 git remote 補齊。"""

    number: int
    base_url: Optional[str] = None
    owner: Optional[str] = None
    repo: Optional[str] = None


@dataclass
class RemoteInfo:
    """解析後的 git remote。``web_base`` 是推得的網站根網址，SSH remote 只能用猜的。"""

    name: str
    host: str
    owner: str
    repo: str
    web_base: Optional[str]
    web_base_guessed: bool


def parse_pr_ref(text: str) -> PrRef:
    """解析 ``128``、``#128`` 或 PR 網址（``…/owner/repo/pulls/128``）。"""
    raw = text.strip()
    match = re.fullmatch(r"#?(\d+)", raw)
    if match:
        return PrRef(number=int(match.group(1)))

    parsed = urllib.parse.urlsplit(raw)
    if parsed.scheme in ("http", "https") and parsed.hostname:
        path_match = _PR_PATH_RE.match(parsed.path)
        if path_match:
            netloc = parsed.hostname
            if parsed.port:
                netloc = f"{netloc}:{parsed.port}"
            return PrRef(
                number=int(path_match.group("num")),
                base_url=f"{parsed.scheme}://{netloc}{path_match.group('prefix')}",
                owner=path_match.group("owner"),
                repo=path_match.group("repo"),
            )
    raise PrSourceError(
        f"看不懂這個 PR 參照：{text!r}。請給 PR 編號（128）或 PR 網址（…/owner/repo/pulls/128）。"
    )


def parse_remote_url(name: str, url: str) -> Optional[RemoteInfo]:
    """解析 git remote URL。認不出 owner/repo 時回傳 ``None``。"""
    raw = url.strip()
    host: Optional[str] = None
    path = ""
    web_base: Optional[str] = None
    guessed = True
    http_prefix_base: Optional[str] = None

    if "://" in raw:
        parsed = urllib.parse.urlsplit(raw)
        host = parsed.hostname
        path = parsed.path
        if parsed.scheme in ("http", "https") and host:
            netloc = f"{host}:{parsed.port}" if parsed.port else host
            http_prefix_base = f"{parsed.scheme}://{netloc}"
            guessed = False
    else:
        scp_match = _SCP_LIKE_RE.match(raw)
        if scp_match:
            host = scp_match.group("host")
            path = scp_match.group("path")

    if not host:
        return None

    segments = [seg for seg in path.strip("/").split("/") if seg]
    if segments and segments[-1].endswith(".git"):
        segments[-1] = segments[-1][: -len(".git")]
    if len(segments) < 2 or not segments[-1]:
        return None

    owner, repo = segments[-2], segments[-1]
    if http_prefix_base is not None:
        prefix = "/".join(segments[:-2])
        web_base = f"{http_prefix_base}/{prefix}" if prefix else http_prefix_base
    else:
        web_base = f"https://{host}"

    return RemoteInfo(
        name=name,
        host=host.lower(),
        owner=owner,
        repo=repo,
        web_base=web_base,
        web_base_guessed=guessed,
    )


def select_remote(
    pr: PrRef, remotes: Dict[str, str], preferred: Optional[str] = None
) -> RemoteInfo:
    """挑出這個 PR 所屬的 remote。

    PR 網址帶有 owner/repo 時，以它比對 remote；只有編號時用 ``preferred``
    （預設 ``origin``），repo 只有一個 remote 時直接用那一個。
    """
    parsed: List[RemoteInfo] = []
    for name, url in remotes.items():
        info = parse_remote_url(name, url)
        if info:
            parsed.append(info)
    if not parsed:
        raise PrSourceError("這個 repo 沒有可辨識的 git remote。")

    if preferred:
        for info in parsed:
            if info.name == preferred:
                return info
        raise PrSourceError(f"找不到名為 {preferred!r} 的 remote。")

    if pr.owner and pr.repo:
        wanted = (pr.owner.lower(), pr.repo.lower())
        matches = [r for r in parsed if (r.owner.lower(), r.repo.lower()) == wanted]
        if not matches:
            known = "、".join(f"{r.name}（{r.owner}/{r.repo}）" for r in parsed)
            raise PrSourceError(
                f"PR 網址指向 {pr.owner}/{pr.repo}，但目前的 repo 沒有對應的 remote（現有：{known}）。"
                "請切到那個專案的資料夾再執行。"
            )
        for info in matches:
            if info.name == "origin":
                return info
        return matches[0]

    for info in parsed:
        if info.name == "origin":
            return info
    if len(parsed) == 1:
        return parsed[0]
    names = "、".join(r.name for r in parsed)
    raise PrSourceError(f"有多個 remote（{names}）且沒有 origin，請用 --remote 指定。")


def url_origin(url: Optional[str]) -> Optional[Tuple[str, str, int]]:
    """回傳網址的來源 ``(scheme, 主機, port)``；不是 http(s) 網址時回傳 ``None``。"""
    if not url:
        return None
    try:
        parsed = urllib.parse.urlsplit(url.strip())
        port = parsed.port
    except ValueError:
        return None
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return None
    return (parsed.scheme, parsed.hostname.lower(), port or (443 if parsed.scheme == "https" else 80))


@dataclass
class TokenStore:
    """設定檔與 secret store 的查詢介面（實作在 ``pr_config.py``；這個模組本身不讀任何檔案）。"""

    host_for_origin: Callable[[Optional[Tuple[str, str, int]]], Optional[str]]
    host_for_ssh: Callable[[str], Optional[str]]
    read_token: Callable[[str], Optional[str]]


@dataclass
class ApiAccess:
    """讀取 PR metadata 時要用的 API 網址，以及是否可以附上 token。

    ``source`` 是 API 網址的來源，``token_source`` 是 token 的來源（``"store"``、``"env"`` 或空字串）。
    """

    base_url: Optional[str]
    token: Optional[str]
    notes: List[str] = field(default_factory=list)
    source: str = ""
    token_source: str = ""


def resolve_api_access(
    pr: PrRef,
    remote: RemoteInfo,
    declared_base: Optional[str],
    token: Optional[str],
    store: Optional[TokenStore] = None,
) -> ApiAccess:
    """決定 API 網址，並判斷哪一個 token 可以送出。

    API 網址依序取自：貼上的 PR 網址、HTTP(S) remote、設定檔裡這個 SSH 主機對應的網址、
    ``declared_base``（``GITEA_BASE_URL``）、由 SSH 主機猜出的網址。

    token 只在來源與 API 網址完全相同時才附上：環境變數的 ``token`` 以 ``declared_base`` 為準，
    ``store`` 裡的 token 以存入時指定的網址為準。兩者都符合時用環境變數的（明確指定的覆寫）。
    """
    notes: List[str] = []
    declared = declared_base.strip().rstrip("/") if declared_base else None
    if declared and url_origin(declared) is None:
        notes.append("GITEA_BASE_URL 不是合法的 http(s) 網址，已忽略。")
        declared = None

    if pr.base_url:
        base, source = pr.base_url, "pr_url"
    elif remote.web_base and not remote.web_base_guessed:
        base, source = remote.web_base, "remote"
    else:
        mapped = store.host_for_ssh(remote.host) if store else None
        if mapped:
            base, source = mapped, "config"
        elif declared:
            base, source = declared, "GITEA_BASE_URL"
        else:
            base, source = remote.web_base, "guessed_from_ssh_host"

    base_origin = url_origin(base)
    if pr.base_url and not remote.web_base_guessed and base_origin and base_origin[1] != remote.host:
        notes.append(f"PR 網址的主機（{base_origin[1]}）與 git remote 的主機（{remote.host}）不同，請確認網址沒有貼錯。")

    send: Optional[str] = None
    token_source = ""
    declared_origin = url_origin(declared)
    if token and declared_origin is not None and base_origin == declared_origin:
        send, token_source = token, "env"
    elif store is not None:
        stored_host = store.host_for_origin(base_origin)
        if stored_host:
            stored = store.read_token(stored_host)
            if stored:
                send, token_source = stored, "store"
            else:
                notes.append(f"設定檔列了 {stored_host}，但找不到它的 token；請重新執行 set-token。")

    if send is None and token:
        if declared_origin is None:
            notes.append(
                "環境裡有 GITEA_TOKEN，但沒有用 GITEA_BASE_URL 指明它屬於哪一台 Gitea，所以沒有送出 token。"
                "建議改用 set-token 把 token 存給指定的主機，並把這個環境變數從 shell 設定檔移除。"
            )
        else:
            target = base_origin[1] if base_origin else "（未知）"
            notes.append(f"沒有送出 token：這個 PR 在 {target}，而環境變數裡的 token 屬於 {declared_origin[1]}。")
    return ApiAccess(base_url=base, token=send, notes=notes, source=source, token_source=token_source)


class _SameOriginRedirectHandler(urllib.request.HTTPRedirectHandler):
    """拒絕轉址到不同來源（主機、port 或 https 降成 http），避免 Authorization 標頭外流。"""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[override]
        if url_origin(req.full_url) != url_origin(newurl):
            return None
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _normalize_metadata(data: Dict[str, Any]) -> Dict[str, Any]:
    base = data.get("base") or {}
    head = data.get("head") or {}
    user = data.get("user") or {}
    return {
        "title": data.get("title") or "",
        "body": data.get("body") or "",
        "url": data.get("html_url") or "",
        "state": data.get("state") or "",
        "merged": bool(data.get("merged")),
        "author": user.get("login") or "",
        "base_ref": base.get("ref") or "",
        "base_sha": base.get("sha") or "",
        "head_ref": head.get("ref") or "",
        "head_sha": head.get("sha") or "",
        "merge_base": data.get("merge_base") or "",
        "updated_at": data.get("updated_at") or "",
    }


_MAX_ERROR_BODY = 8192
_MAX_SERVER_MESSAGE = 200


def explain_http_error(
    status: int, message: str, is_json: bool, token_sent: bool, writing: bool = False
) -> Tuple[str, str]:
    """把 API 的錯誤回應翻成 ``(原因代碼, 給使用者的說明)``。

    比對的字串取自 Gitea 的 ``routers/api/v1/api.go``（1.19 到目前的 main）。同樣是 403，原因可能是
    沒有登入、token 的權限範圍不夠、token 只能讀公開的 repo，或帳號沒有這個 repo 的讀取權限，
    要做的事完全不同，所以不能只回報狀態碼。
    """
    lowered = message.lower()
    if status in (401, 403):
        if "required scope" in lowered:
            if writing:
                return "token_scope", (
                    "token 的權限範圍不夠：送出 review 需要 repository 的「讀寫」權限（write:repository），"
                    "請重新產生 token 並勾選它"
                )
            return "token_scope", (
                "token 的權限範圍不夠：讀取 PR 需要 repository 的「讀取」權限（read:repository），"
                "請重新產生 token 並勾選它"
            )
        if "limited to public" in lowered:
            return "token_public_only", "這個 token 被限制成只能讀公開的 repo（public only），讀不到私有 repo 的 PR"
        if "read permission" in lowered or "permission to read" in lowered:
            return "no_repo_access", "token 所屬的帳號沒有讀取這個 repo 的權限"
        if not is_json:
            return "blocked", "回應不是 Gitea API 的格式，請求可能在到達 Gitea 之前就被 proxy、SSO 或防火牆擋下"
        if not token_sent:
            return "login_required", "這台 Gitea 要登入才能使用 API，而這次的請求沒有帶 token（在 review 頁面最上方的「連接 Gitea」貼上 token，或用 set-token 存入）"
        if status == 401 or "signed in" in lowered or "token" in lowered:
            return "token_rejected", "帶了 token 但沒有被接受：token 可能已撤銷、過期或貼錯"
        return "forbidden", "伺服器拒絕了這個請求"
    if status == 404:
        if token_sent:
            return "not_found", "找不到這個 PR，或 token 所屬的帳號看不到這個 repo"
        return "not_found", "找不到這個 PR；私有的 repo 在沒有帶 token 時也會回 404"
    if status == 422:
        # 送出 review 時 Gitea 的幾條規則（preparePullReviewType，1.19 到目前的 main 都一樣）
        if "approve your own pull" in lowered:
            return "own_pull", "不能核准自己開的 PR，請改選「只留言」"
        if "reject your own pull" in lowered:
            return "own_pull", "不能對自己開的 PR 要求修改，請改選「只留言」"
        if "requires a body or a comment" in lowered:
            return "nothing_to_send", "沒有可以送出的內容：至少要有一則留言或一段整體說明"
        if "requires a body" in lowered:
            return "body_required", "「要求修改」一定要寫整體說明"
        return "rejected", "Gitea 不接受這次送出的內容"
    return "server_error", "伺服器回應錯誤"


def _server_message(exc: urllib.error.HTTPError, token: Optional[str]) -> Tuple[str, bool]:
    """取出錯誤回應裡的說明（Gitea 的格式是 ``{"message": …}``）。回傳 ``(說明, 回應是不是 JSON)``。"""
    try:
        text = exc.read(_MAX_ERROR_BODY).decode("utf-8", "replace")
        payload = json.loads(text)
    except Exception:  # noqa: BLE001 - 讀不到或不是 JSON 都只代表「沒有說明」
        return "", False
    message = payload.get("message") if isinstance(payload, dict) else None
    if not isinstance(message, str):
        return "", True
    message = " ".join(message.split())
    if token:
        message = message.replace(token, "***")
    return message[:_MAX_SERVER_MESSAGE], True


def _api_get(url: str, token: Optional[str], timeout: float) -> Any:
    """對 Gitea API 發一個唯讀的 GET，回傳解析後的 JSON；失敗時丟出帶原因的 :class:`PrMetadataError`。"""
    return _api_request(url, token, timeout)


def _api_request(url: str, token: Optional[str], timeout: float, payload: Optional[Dict[str, Any]] = None) -> Any:
    """對 Gitea API 發一個請求：沒有 ``payload`` 時是 GET，有的話以 JSON 內容 POST。"""
    host = urllib.parse.urlsplit(url).hostname
    headers = {"Accept": "application/json", "User-Agent": USER_AGENT}
    body = None
    if payload is not None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=body, headers=headers, method="POST" if payload is not None else "GET")
    if token:
        request.add_header("Authorization", f"token {token}")

    opener = urllib.request.build_opener(_SameOriginRedirectHandler())
    try:
        with opener.open(request, timeout=timeout) as response:
            body = response.read()
    except urllib.error.HTTPError as exc:
        try:
            if exc.code in (301, 302, 303, 307, 308):
                target = url_origin(exc.headers.get("Location") if exc.headers else None)
                where = f"{target[0]}://{target[1]}" if target else "別的網址"
                raise PrMetadataError(
                    f"HTTP {exc.code}：伺服器把請求轉到 {where}（常見於 SSO 登入頁，或 http 轉 https）；"
                    "為了不讓 token 外流，沒有跟過去",
                    status=exc.code, cause="redirected",
                ) from exc
            message, is_json = _server_message(exc, token)
            cause, text = explain_http_error(exc.code, message, is_json, bool(token), writing=payload is not None)
            detail = f"HTTP {exc.code}：{text}"
            if message:
                detail += f"。伺服器的說明：「{message}」"
            raise PrMetadataError(detail, status=exc.code, cause=cause, server_message=message) from exc
        finally:
            exc.close()
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise PrMetadataError(f"連不上 {host}：{exc}", cause="unreachable") from exc

    if payload is not None and not body.strip():
        return None  # 寫入成功但沒有內容（例如解決討論回的是 204）
    try:
        return json.loads(body.decode("utf-8"))
    except ValueError as exc:
        raise PrMetadataError(
            f"{host} 回應的不是 JSON（可能被 SSO 登入頁或 proxy 攔截，或這個網址不是 Gitea）",
            status=200, cause="blocked",
        ) from exc


def fetch_pr_metadata(
    base_url: str,
    owner: str,
    repo: str,
    number: int,
    token: Optional[str] = None,
    timeout: float = 15.0,
) -> Dict[str, Any]:
    """向 Gitea 讀取單一 PR 的 metadata（``GET /api/v1/repos/{owner}/{repo}/pulls/{index}``）。"""
    url = "{base}/api/v1/repos/{owner}/{repo}/pulls/{number}".format(
        base=base_url.rstrip("/"),
        owner=urllib.parse.quote(owner, safe=""),
        repo=urllib.parse.quote(repo, safe=""),
        number=int(number),
    )
    payload = _api_get(url, token, timeout)
    if not isinstance(payload, dict) or "head" not in payload:
        raise PrMetadataError(
            "回應不是預期的 PR 格式（這台主機可能不是 Gitea，或 API 路徑不同）", cause="unexpected"
        )
    return _normalize_metadata(payload)


def check_repo_access(
    base_url: str, owner: str, repo: str, token: Optional[str] = None, timeout: float = 15.0
) -> None:
    """確認目前的身分讀得到這個 repo（``GET /api/v1/repos/{owner}/{repo}``，需要 repository 的讀取權限）。"""
    url = "{base}/api/v1/repos/{owner}/{repo}".format(
        base=base_url.rstrip("/"),
        owner=urllib.parse.quote(owner, safe=""),
        repo=urllib.parse.quote(repo, safe=""),
    )
    payload = _api_get(url, token, timeout)
    if not isinstance(payload, dict) or "full_name" not in payload:
        raise PrMetadataError("回應不是預期的 repo 格式（這台主機可能不是 Gitea）", cause="unexpected")


def fetch_server_version(base_url: str, token: Optional[str] = None, timeout: float = 15.0) -> str:
    """讀取 Gitea 的版本（``GET /api/v1/version``），用來分辨「連不上 API」與「只有這個 PR 讀不到」。"""
    payload = _api_get(f"{base_url.rstrip('/')}/api/v1/version", token, timeout)
    version = payload.get("version") if isinstance(payload, dict) else None
    if not isinstance(version, str) or not version:
        raise PrMetadataError("回應裡沒有版本資訊（這台主機可能不是 Gitea）", cause="unexpected")
    return version[:40]


# 「解決討論」的 API（POST …/pulls/comments/{id}/resolve）從 Gitea 1.26 才有；
# 依 routers/api/v1/api.go：release/v1.25 沒有，release/v1.26 與 main 有。
_RESOLVE_MIN_VERSION = (1, 26)


def gitea_version(version: str) -> Optional[Tuple[int, int]]:
    """把 ``/api/v1/version`` 回報的字串轉成 ``(主版號, 次版號)``；認不出來時回傳 None。

    Forgejo 回報的是自己的版號加上相容的 Gitea 版號（例如 ``11.0.3+gitea-1.22.0``），以後者為準，
    不然會把 Forgejo 11 當成比 Gitea 1.26 新。
    """
    match = re.search(r"gitea-(\d+)\.(\d+)", version) or re.match(r"v?(\d+)\.(\d+)", version.strip())
    return (int(match.group(1)), int(match.group(2))) if match else None


def supports_resolve(version: str) -> Optional[bool]:
    """這個版本的 Gitea 能不能用 API 解決／重新開啟一串 review 討論。

    認不出版本（沒讀到，或不是版號的字串）時回傳 None：那是「不知道」，不是「不支援」，
    頁面在這種時候不顯示按鈕，也不說版本不夠。
    """
    parsed = gitea_version(version)
    return None if parsed is None else parsed >= _RESOLVE_MIN_VERSION


# --------------------------------------------------------------------------- review 的讀取與送出

REVIEW_EVENTS = ("COMMENT", "APPROVED", "REQUEST_CHANGES")
_PAGE_SIZE = 50
_MAX_PAGES = 20


def _repo_api(base_url: str, owner: str, repo: str) -> str:
    return "{base}/api/v1/repos/{owner}/{repo}".format(
        base=base_url.rstrip("/"),
        owner=urllib.parse.quote(owner, safe=""),
        repo=urllib.parse.quote(repo, safe=""),
    )


def _paged(url: str, token: Optional[str], timeout: float) -> List[Dict[str, Any]]:
    """讀完一個分頁的清單端點。"""
    items: List[Dict[str, Any]] = []
    for page in range(1, _MAX_PAGES + 1):
        separator = "&" if "?" in url else "?"
        chunk = _api_get(f"{url}{separator}limit={_PAGE_SIZE}&page={page}", token, timeout)
        if not isinstance(chunk, list):
            break
        items.extend(item for item in chunk if isinstance(item, dict))
        if len(chunk) < _PAGE_SIZE:
            break
    return items


def fetch_current_user(base_url: str, token: str, timeout: float = 15.0) -> str:
    """回傳 token 所屬帳號的登入名稱（``GET /api/v1/user``，需要 user 的讀取權限）。"""
    payload = _api_get(f"{base_url.rstrip('/')}/api/v1/user", token, timeout)
    login = payload.get("login") if isinstance(payload, dict) else None
    if not isinstance(login, str) or not login:
        raise PrMetadataError("回應裡沒有帳號名稱", cause="unexpected")
    return login


def fetch_reviews(
    base_url: str, owner: str, repo: str, number: int, token: Optional[str] = None, timeout: float = 15.0
) -> Dict[str, List[Dict[str, Any]]]:
    """讀取這個 PR 上既有的 review 與行內留言。

    回傳 ``{"reviews": [...], "comments": [...]}``。留言的 ``line`` 是它留下當時的行號：
    Gitea 的 ``position`` 是新檔行號、``original_position`` 是舊檔行號（留在被刪除的行上）。
    """
    root = f"{_repo_api(base_url, owner, repo)}/pulls/{int(number)}/reviews"
    reviews: List[Dict[str, Any]] = []
    comments: List[Dict[str, Any]] = []
    for raw in _paged(root, token, timeout):
        review_id = raw.get("id")
        user = (raw.get("user") or {}).get("login") or ""
        state = raw.get("state") or ""
        if not isinstance(review_id, int) or state == "PENDING":
            continue
        reviews.append(
            {
                "id": review_id,
                "user": user,
                "state": state,
                "body": raw.get("body") or "",
                "commit_id": raw.get("commit_id") or "",
                "stale": bool(raw.get("stale")),
                "dismissed": bool(raw.get("dismissed")),
                "submitted_at": raw.get("submitted_at") or "",
                "url": raw.get("html_url") or "",
            }
        )
        if not raw.get("comments_count", 1):
            continue
        for item in _paged(f"{root}/{review_id}/comments", token, timeout):
            old_line = item.get("original_position") or 0
            new_line = item.get("position") or 0
            comments.append(
                {
                    "id": item.get("id"),
                    "review_id": review_id,
                    "user": (item.get("user") or {}).get("login") or user,
                    "body": item.get("body") or "",
                    "path": item.get("path") or "",
                    "side": "old" if old_line and not new_line else "new",
                    "line": (old_line if old_line and not new_line else new_line) or None,
                    "commit_id": item.get("commit_id") or "",
                    "diff_hunk": item.get("diff_hunk") or "",
                    "resolved": bool(item.get("resolver")),
                    "created_at": item.get("created_at") or "",
                    "url": item.get("html_url") or "",
                }
            )
    return {"reviews": reviews, "comments": comments}


def list_open_pulls(
    base_url: str, owner: str, repo: str, token: Optional[str] = None, timeout: float = 15.0
) -> List[Dict[str, Any]]:
    """列出這個 repo 還開著的 PR（``GET …/pulls?state=open``），最近更新的排前面。

    ``requested_reviewers`` 是被請求 review 的帳號清單；Gitea 1.19 的回應沒有這一欄，那時是 None，
    代表「這台 Gitea 不提供這項資訊」，和「沒有人被請求」（空清單）不同。
    """
    pulls: List[Dict[str, Any]] = []
    for raw in _paged(f"{_repo_api(base_url, owner, repo)}/pulls?state=open&sort=recentupdate", token, timeout):
        if not isinstance(raw.get("number"), int):
            continue
        requested = raw.get("requested_reviewers") if "requested_reviewers" in raw else None
        pulls.append(
            {
                "number": raw["number"],
                "title": raw.get("title") or "",
                "author": (raw.get("user") or {}).get("login") or "",
                "url": raw.get("html_url") or "",
                "head_sha": (raw.get("head") or {}).get("sha") or "",
                "base_ref": (raw.get("base") or {}).get("ref") or "",
                "draft": bool(raw.get("draft")),
                "updated_at": raw.get("updated_at") or "",
                "requested_reviewers": (
                    None if requested is None
                    else [user.get("login") or "" for user in requested or [] if isinstance(user, dict)]
                ),
            }
        )
    return pulls


def set_comment_resolved(
    base_url: str, owner: str, repo: str, comment_id: int, token: str, resolved: bool, timeout: float = 30.0
) -> None:
    """把一則 review 留言所在的討論標成已解決，或重新開啟（``POST …/pulls/comments/{id}/resolve|unresolve``）。

    Gitea 1.26 以上才有這個 API；能不能操作由 Gitea 判斷（PR 的作者，或對這個 repo 有寫入權限的人）。
    """
    action = "resolve" if resolved else "unresolve"
    url = f"{_repo_api(base_url, owner, repo)}/pulls/comments/{int(comment_id)}/{action}"
    try:
        _api_request(url, token, timeout, {})
    except PrMetadataError as exc:
        if exc.status in (404, 405):
            raise PrMetadataError(
                "這台 Gitea 還不能從這裡解決討論（需要 1.26 以上），或這則留言已經不在了；請到 Gitea 上操作",
                status=exc.status, cause="unsupported",
            ) from exc
        if exc.status == 403 and exc.cause != "token_scope":
            raise PrMetadataError(
                "這個帳號不能解決這串討論：要是 PR 的作者，或對這個專案有寫入權限",
                status=403, cause="forbidden",
            ) from exc
        raise


def create_review(
    base_url: str,
    owner: str,
    repo: str,
    number: int,
    token: str,
    event: str,
    body: str,
    commit_id: str,
    comments: List[Dict[str, Any]],
    timeout: float = 30.0,
) -> Dict[str, Any]:
    """送出一份 review（``POST …/pulls/{index}/reviews``）。本模組會寫入 Gitea 的函式只有兩個：這一個，以及 :func:`set_comment_resolved`。

    ``comments`` 的每一項是 ``{"path", "body", "side", "line"}``；Gitea 的行內留言只能掛在單一行上。
    """
    if event not in REVIEW_EVENTS:
        raise PrMetadataError(f"不支援的 review 類型：{event!r}", cause="invalid")
    payload = {
        "event": event,
        "body": body,
        "commit_id": commit_id,
        "comments": [
            {
                "path": item["path"],
                "body": item["body"],
                "new_position": int(item["line"]) if item.get("side") != "old" else 0,
                "old_position": int(item["line"]) if item.get("side") == "old" else 0,
            }
            for item in comments
        ],
    }
    result = _api_request(f"{_repo_api(base_url, owner, repo)}/pulls/{int(number)}/reviews", token, timeout, payload)
    if not isinstance(result, dict) or "id" not in result:
        raise PrMetadataError("送出後的回應不是預期的 review 格式", cause="unexpected")
    return {"id": result["id"], "state": result.get("state") or event, "url": result.get("html_url") or ""}
