# Access and Credential Handling

## Goal

用最低摩擦處理 Figma 與 Axure 的權限問題，同時避免把 secrets 放進 repo 或文件內容。

---

## Global rules

- 不將 secrets 放入 repo（包含 repo 內任何 `.local` 檔案或專案目錄下的明文 secret）。
  - 注意：這裡禁止的是「**專案目錄內**」的明文 secret；非 macOS backend 使用的
    `${XDG_DATA_HOME:-~/.local/share}/feature-spec-builder/secrets.json` 位於使用者家目錄、不在任何 repo 內，符合此原則。
- 不將 token / access code / 帶 code 的完整 URL 寫進：
    - `FEATURE-SPEC.md`
    - `Change Log`
    - 一般輸出
    - prompt 範本
- 長期保存憑證由 `keychain_helper.py` 管理，後端依平台自動選擇：
    - **macOS** → macOS Keychain（`security` CLI），Service: `com.claude.feature-spec-builder`
    - **其他平台** → `${XDG_DATA_HOME:-~/.local/share}/feature-spec-builder/secrets.json`（檔案權限 `0600`）
    - 存入：`echo "<token>" | python3 keychain_helper.py store`
    - 檢查：`python3 keychain_helper.py check`（不印出 token）
    - 刪除：`python3 keychain_helper.py delete`
- Token 解析優先順序（由 `extract_figma_page.py` 內部 `resolve_token` 處理）：
    1. `--token` 參數
    2. `FIGMA_ACCESS_TOKEN` 環境變數
    3. 本機 secret store（Keychain 或 0600 檔案）
- Axure access code 解析優先順序（由 `extract_axure_page.py` 處理）：
    1. `--code` 參數
    2. `AXURE_ACCESS_CODE` 環境變數
    3. 本機 secret store
- 所有 secrets 更新都屬於「覆蓋既有值」，不是附加保存。
- macOS `security` CLI 在寫入時有短暫的 process-level exposure，這是 Apple 工具的已知限制，無替代方案。
  非 macOS 的檔案後端以 `0600` 權限寫入，僅當前使用者可讀。
- 注意：首次存入時 token 會經過 Agent 對話 context 一次，後續使用由腳本內部從 secret store 讀取，不再進入
  context。

---

## Figma

### Expected access model

- 使用者層級 Figma access token
- 搭配 file/page/frame links 使用
- 日常流程應該是「平常只貼 link；缺 token 時才補 token」

### Read flow

1. 執行 `extract_figma_page.py`，腳本內部依序查 `--token` > env var > Keychain
2. 若取得 token 且讀取成功，繼續 spec intake
3. 若腳本回報 token 不存在：
    - 執行 `keychain_helper.py check` 確認 Keychain 狀態
    - 向使用者索取 token
    - 取得後執行 `echo "<token>" | python3 keychain_helper.py store`
    - 重新執行 `extract_figma_page.py`
4. 若腳本回報 API 403/401（token 無效）：
    - 告知使用者 token 已失效
    - 取得新 token 後以 `keychain_helper.py store` 覆蓋
5. 若 token 有效但仍 denied：
    - 提示檢查該 file 權限或重給正確 link

### If missing token

Skill 應明確要求：

- 請提供 Figma access token

並在取得後：

- 執行 `echo "<token>" | python3 keychain_helper.py store` 存入 macOS Keychain
- 後續由腳本內部自動從 Keychain 讀取，不再進入 Agent context
- 不回顯 token 原文

### If token invalid

Skill 應明確要求：

- 目前 Figma token 無效或已失效，請提供新的 token

並在取得後：

- 執行 `echo "<new_token>" | python3 keychain_helper.py store` 覆蓋舊值
- `keychain_helper.py store` 會自動先刪除再新增，不保留多個歷史 token
- 不把舊 token 寫到任何 log

### If permission denied but token exists

Skill 應提示：

- Token 已存在，但目前對該 Figma file / page / frame 無存取權限
- 請確認該檔案的 view 權限
- 或重新提供正確 link

### What “auto update” means

這裡的「自動更新」定義為：

- 缺 token 時自動要求使用者提供
- token 失效時自動要求新的 token
- 取得後自動覆蓋保存為預設

不是：

- 系統自行向 Figma refresh token
- 或自動取得新 PAT

---

## Axure

### Expected access model

- 以 share link 為主
- 如需要 access code，則由使用者提供
- Skill 保存的是「share link 對應 access code」，不是永久保存完整帶 code 的 URL

### Read flow

1. 嘗試讀取 Axure share link
2. 若成功，直接繼續
3. 若失敗，判斷是：
    - 需要 access code
    - access code 錯誤
    - share link 失效 / 被停用
    - 只有 workspace / SSO 成員可讀
    - link 本身格式錯誤

### If access code required

Skill 應明確要求：

- 請提供此 Axure share link 對應的 access code

取得後：

- 執行 `echo "<code>" | python3 keychain_helper.py axure-store --link "<share_link>"` 存入 Keychain
- 後續遇到相同 share link 時，先 `axure-check`，若有則 `axure-get` 自動取用
- 執行時動態注入，不要把帶 code 的完整 URL 長期保存或回顯

### If access code invalid

Skill 應提示：

- 目前 access code 無效，請重新確認正確的 access code

並在取得新 code 後：

- 覆蓋舊的對應值

### If not an access-code problem

若表現更像以下狀況：

- share link 失效
- share link 被停用
- 只有 workspace / SSO 成員可讀

則不要再要求 access code。  
改為要求：

- 新的可用 share link
- 或匯出 PDF / screenshots / flow summary

### Dynamic injection rule

正確做法：

- 保存 `share_link -> access_code` 對應
- 真正請求前才拼接或注入
- 對外輸出時不顯示完整帶 code URL

不正確做法：

- 將完整帶 code 的 URL 長期保存
- 將帶 code 的 URL 寫到 spec 或 log

---

## What the skill should ask for

### Figma missing access

最少要問：

- Figma access token
- 若 token 已有但 still denied，則問是否確認 file 權限或重給正確 link

### Axure missing access

最少要問：

- 是否有 access code
- 若有，請提供 access code
- 若沒有或提供後仍無法讀取，請提供新的 share link 或匯出資產

---

## Safe persistence policy

Figma token 由 `keychain_helper.py` 管理，依平台保存到 macOS Keychain 或 `0600` 檔案（見上方 Global rules）。
Axure access code 以 JSON mapping 保存（一筆 entry，key 為 share link，value 為 code）：

- 存入：`echo "<code>" | python3 keychain_helper.py axure-store --link "<share_link>"`
- 查詢：`python3 keychain_helper.py axure-get --link "<share_link>"`（印出 code，供 Agent 搭配 WebFetch
  使用）
- 檢查：`python3 keychain_helper.py axure-check --link "<share_link>"`（exit 0=有，exit 1=無）
- 刪除：`python3 keychain_helper.py axure-delete --link "<share_link>"`
- 注意：Agent 需要 code 來搭配 WebFetch，因此 `axure-get` 會印出 code 到 stdout，code 會進入 Agent
  context。

永遠不要：

- 保存到專案目錄（含 repo 內任何 `.local` 檔案）
- 保存到 `FEATURE-SPEC.md`
- 讓 token 出現在 Agent 對話輸出中（`keychain_helper.py get` 會透過 stdout
  傳給呼叫腳本，但僅限腳本間內部傳遞，不可直接對使用者輸出）

---

## Recommended user-facing wording

### Figma missing token

- 無法讀取 Figma：目前缺少可用的 Figma access token。請提供 token；保存後，下次會自動沿用。

### Figma token invalid

- 無法讀取 Figma：目前保存的 token 已失效或無效。請提供新的 token，我會覆蓋舊值。

### Figma permission denied

- 無法讀取 Figma：token 存在，但目前對此檔案或節點沒有權限。請確認 file 權限或重新提供正確 link。

### Axure needs access code

- 無法讀取 Axure：這個 share link 需要 access code。請提供 access code；保存後，同一連結下次會自動套用。

### Axure link invalid or restricted

- 無法讀取 Axure：這看起來不是 access code 問題，可能是 share link 失效、被停用，或僅限 workspace / SSO
  成員。請提供新的可用 share link，或改提供 PDF / 截圖 / flow summary。