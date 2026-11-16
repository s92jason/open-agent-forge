# Operating Procedure

## Completion Contract（完成契約 — 跨 harness 防斷流）

**本 skill 的「完成」定義：只有 Phase 4 Validate 全數通過後才算完成**（Code Sync mode 則為 CS-4 + Phase 4）。產出 `FEATURE-SPEC.md` 檔案本身 **不等於** 完成 —— 它只是 Phase 3 的草稿產物，後面還有 Phase 3.5 與 Phase 4。

執行期間，**唯一允許停下並把控制權交還使用者的時機只有以下三個**：

1. Phase 1 Intake 的逐一提問（含 Step 9 抓取確認 gate）
2. Phase 1.5 Step 1.5.3 的批次補憑證 / 補 URL
3. Phase 3.5 Step 3 的問題清單（對使用者可見）——**當 Q&A Gate 判定需要提問時，這是強制停點，不是可選**；詳見 `post-draft-qa-checklist.md` 的「Q&A Gate」

除上述三點外，**任何 phase 之間都不得停下、不得回報「完成」、不得等待使用者指示**—— 尤其是 Phase 3 產出文件之後，必須立即接續 Phase 3.5。若你發現自己「剛吐完整份 spec、正想收手」，那正是最常見的斷流點：請繼續往下走，不要停。

> 給 Codex / 非 Claude harness 的提醒：產出大型 artifact 後若無此契約，模型傾向 yield 回使用者。請把上面三個停止點當成 hard gate，其餘一律連續執行到 Phase 4。

## Phase 1: Intake

**核心原則：一次只問一個問題。** 等使用者回答後再問下一個，絕對不能把多個問題合併在同一則訊息輸出。
*例外：Step 1 模式選單、Update mode 菜單、Phase 3.5 Q&A、Code Sync CS-3 報告勾選等明確列出「選項/動作分類」的場景不受此限。*

**收集 vs 抓取分離原則：** Step 5 / Step 6 / Step 6.1 收集設計資源（Axure / Figma / API）期間，**不觸發任何 extractor**；所有資源在 Phase 1 全部收齊、通過 Step 9 confirm gate 後，才於 Phase 1.5 統一批次抓取。對應使用者期望：「等我全部給完時，再去抓，有問題時，再跳出要詢問的問題」。

**快速跳過規則：** 若使用者第一則訊息已提供多項資訊（例如同時給了 feature name、Axure link、Figma
link），跳過已回答的步驟，只問尚缺的項目。不要重複確認使用者已明確提供的內容。

### Step 1：確認模式（若使用者第一句未明確指出）

詢問並提供選項：

```
這次要做什麼？
A. Create — 全新建立 FEATURE-SPEC.md
B. Update — 更新現有 FEATURE-SPEC.md（菜單式，挑要動的面向）
C. Code Sync — feature 收尾時，以目前程式碼為事實基礎反向驗證 spec
```

### Step 2：依模式分支

- **A. Create mode** → 繼續執行下方 Step 3 ~ Step 8。
- **B. Update mode** → **跳過 Step 3 ~ Step 6**，改走 `references/update-mode-menu.md` 的菜單流程（內含 read-first 萃取 Feature Name 機制，不再重問名稱）；菜單結束後從 Step 7 / Step 8 必要項補檢，再進 Phase 2。
- **C. Code Sync mode** → 跳過下方所有 Step，改走 `references/code-sync-procedure.md` 的 CS-1 ~ CS-4 流程（同樣採 read-first 萃取 Feature Name）。

---

以下 Step 3 ~ Step 6 **僅 Create mode 執行**；Update mode 與 Code Sync mode 各自有專屬流程。

### Step 3：確認 Feature 名稱（Create mode；若未提供）

### Step 4：確認 Feature 目標路徑（Create mode 必問）

詢問：

```
這個 Feature 的目錄路徑是什麼？
（例如：app/src/main/java/com/example/app/feature/）
FEATURE-SPEC.md 將存放在該目錄下。
```

### Step 5：取得 Axure link（Create mode；若未提供）

收到第一個 link 後，詢問：「還有其他 Axure link 嗎？有的話繼續提供；沒有了就說「完成」/「沒了」/「done」。」
持續收集，直到使用者明確表示結束。**本 step 結束時只把這批 URL 加入待抓清單，不呼叫 extractor**（實際抓取在 Phase 1.5 批次執行）。

### Step 6：取得 Figma link（Create mode；若未提供）

說明可提供的類型（file link、page link、frame link），請使用者逐批提供。
每收到一批後詢問：「還有其他 Figma link 嗎？有的話繼續提供；沒有了就說「完成」/「沒了」/「done」。」
持續收集，直到使用者明確表示結束。**本 step 結束時只把這批 URL 加入待抓清單，不呼叫 extractor**。

建議最低標準（提醒但不強制卡關）：
- 1 個 file link + 1 個 page link + 至少 3 個 key frame links
- 若使用者表示結束但未達最低標準，提醒一次後尊重使用者決定繼續

### Step 6.1：取得 API doc（Create mode **必問**，多輪收集）

收到第一份 API 文件後，詢問：「還有其他 API 文件嗎？有的話繼續提供；沒有了就說「完成」/「沒了」/「done」。」
持續收集（同 Axure / Figma 的多輪 pattern），直到使用者明確表示結束。**API 文件本身為文字，不經 extractor，但同樣納入 Step 9 摘要供使用者確認**。

- 若使用者明確說「目前沒有」（第一份就沒給）→ 繼續流程，文件狀態改為 `Pending API confirmation`，🔌 API 規格章節標記 `[Pending]`。
- 所有收集到的 API 文件納入 Phase 2 Reconcile 時逐份比對；附錄 A 型別定義收齊所有 endpoint。

> Update mode 的 API 補充透過菜單選項 C 處理，沿用同一多輪 pattern，不在此步驟。

### Step 6.5：其他補充資料（視需要逐一詢問）
code path、補充說明等，有需要時再詢問。

### Step 7：Figma token 確認（Create mode 主動執行；Update mode 於菜單選項 B 觸發時 lazy-load；Code Sync mode 不需要）

執行 `keychain_helper.py check`（exit 0 = 已有 token，exit 1 = 無 token）：

- exit 0：靜默繼續
- exit 1：向使用者索取，取得後執行 `echo "<token>" | python3 keychain_helper.py store` 存入 Keychain
- 若後續 API 回 403/401：告知 token 失效，重新索取並覆蓋

其他權限問題依 `access-and-credential-handling.md` 處理。

### Step 8：讀取或建立專案設定（三種模式都執行）

讀取 `${XDG_DATA_HOME:-~/.local/share}/feature-spec-builder/{project-key}.json`（project-key = git repo
根目錄名稱，sanitize 為 `[a-zA-Z0-9_-]`，其餘替換為 `_`）：

- 若有 `coding_standard`：靜默套用，Reconcile 時一併考量
- 若無：詢問「這個專案是否有 coding standard 文件？若有請提供路徑；若無請說「沒有」。這個答案會記住。」

### Step 9：資源蒐集摘要與抓取確認 gate（Create mode；Update mode 由菜單 H 觸發、Code Sync mode 跳過）

Step 5 / 6 / 6.1 都結束、Step 7 / 8 也走完後，**先不要直接呼叫 extractor**。列出本次蒐集到的所有待抓資源摘要，例如：

```
這次要抓的全部來源：
  Axure: 3 個 URL
  Figma: 5 個 URL（其中 1 file / 1 page / 3 frame）
  API doc: 2 份（已收為文字，不需 extractor）

以上是要抓的全部來源，要開始抓取嗎？(y / n / 我還要補)
```

使用者選項：

- `y`（或等義回覆「開始」「好」「go」等）→ 進入 **Phase 1.5 批次抓取**
- `n` 或「我還要補 Figma / Axure / API」→ 回對應 Step 補完該批 URL，再回到 Step 9 重新顯示摘要
- 若使用者改主意要刪除某條 URL → 從待抓清單移除後，回 Step 9 重新顯示摘要

**重要**：使用者可能在 Step 9 反覆「補一個 → 回 gate」，這是預期行為；每次補完都要重列完整摘要，避免使用者忘了已貼過哪些。

> Update mode 沒有獨立的「Step 9」，但菜單 H 觸發抓取前同樣要顯示本次累積的 URL 摘要並確認，邏輯共用本 step。

### Phase 1 收尾與下一階段路徑

依模式進入對應階段：

- **Create mode**：Step 9 confirm gate 通過後，進入 Phase 1.5 Source Extraction。
- **Update mode**：菜單流程（`references/update-mode-menu.md`）走完且使用者選 `H` 後，視菜單選項決定是否需要局部執行 Phase 1.5（A/B 選項才需，且同樣套用 Step 9 confirm gate 邏輯），再進入 **Phase 2 Reconcile（局部模式）**。
- **Code Sync mode**：完全跳過 Phase 1.5，直接走 `references/code-sync-procedure.md` 的 CS-2 ~ CS-4，**不進 Phase 2 / Phase 3.5**，僅在 CS-4 完成後跑 **Phase 4 Validate**。

## Phase 1.5: Source Extraction

**統一入口：所有 Figma / Axure 抽取都透過 `scripts/extract_with_cache.py` wrapper。** 不直接呼叫 `extract_figma_page.py` 或 `extract_axure_page.py`。

**執行時機與順序**：
- **統一在 Phase 1 Step 9 confirm gate 通過後才執行**，絕對不要在使用者貼第一個 URL 當下就抓。
- 對 Phase 1 蒐集到的所有 URL **依序**（sequential）呼叫 wrapper：先跑完所有 Figma，再跑完所有 Axure（或相反順序皆可，視實作便利）。
- **單個 URL 失敗不阻斷其他 URL**：失敗訊息累積到 Step 1.5.3 批次匯報，**不要在抓取中途向使用者索取憑證或停下流程**。

完整 cache 規則見 `references/cache-policy.md`，重點摘要：

- 規則：wrapper 先查 cache，hit 跳過 extractor、miss 呼叫 extractor
- 例外：**Update menu A/B** 路徑下，wrapper 加 `--bust-cache` flag（重列 URL = 使用者明示要 refetch）
- 檔案：每個 link 一份獨立 JSON 在 `<feature>/figma/<hash>.json` 或 `<feature>/axure/<hash>.json`，hash = `sha256("<type>|<url>|<page>")[:8]`

### Step 1.5.0：定位腳本絕對路徑（每次 Phase 1.5 開頭做一次）

skill 的安裝位置因 harness 而異（Claude Code 的 plugins 目錄、Codex 的 skills 目錄、antigravity workspace…），**不能假設 cwd 就是 skill 目錄、也不能假設 `scripts/...` 相對路徑跑得起來**。進 Step 1.5.1 前，先解析出本 skill `scripts/` 的絕對路徑（下文記為 `<scripts-dir>`），後續所有腳本呼叫一律用它。

- 你正在讀的這份 `operating-procedure.md` 位於 `<skill-dir>/references/`，故 `<scripts-dir>` = 與 `references/` 同層的 `scripts/`（即把讀檔路徑的 `references/operating-procedure.md` 換成 `scripts/`）。
- 開始批次抓取前，先確認 `<scripts-dir>/extract_with_cache.py` 確實存在。

### Step 1.5.1：Figma 批次抽取

對 Phase 1 蒐集到的**每個** Figma URL 依序執行 wrapper（token 由底層 extractor 自動從 Keychain 讀取）：

```bash
python3 <scripts-dir>/extract_with_cache.py \
  figma "<figma-url>" --page "<page-name>" \
  --feature-dir <repo-root>/.ai-artifacts/feature-spec-builder/<feature-name> \
  [--bust-cache]   # 僅 Update menu B 路徑下加
```

- 成功時 stdout 印 `CACHE_HIT: <path>` 或 `EXTRACTED: <path>`，讀該 path 取得 frame 列表、文字內容與推測狀態
- **失敗處理（不 inline 詢問）**：
    - 若腳本回報缺 token / token 失效（401/403）→ 把該 URL 記入「Figma token 失效」清單，繼續跑下一個
    - 若回報 rate limit（429）→ 記入「rate limit」清單，繼續跑下一個
    - 若抽取失敗（URL 無效、權限不足、結構異常等）→ 記入「其他錯誤」清單，繼續跑下一個
- 失敗訊息一律累積到 Step 1.5.3 統一處理；不要中途呼叫 `keychain_helper.py store` 或向使用者索取

### Step 1.5.2：Axure 批次抽取

對 Phase 1 蒐集到的**每個** Axure share link（`<id>.axshare.com`）依序執行：

```bash
python3 <scripts-dir>/extract_with_cache.py \
  axure "<axure-url>" \
  --feature-dir <repo-root>/.ai-artifacts/feature-spec-builder/<feature-name> \
  [--bust-cache]   # 僅 Update menu A 路徑下加
```

- 抓取前可先用 `keychain_helper.py axure-check --link "<url>"` 檢查 Keychain：若已存 access code，wrapper 會自動讀取並抓取
- **缺 access code 時不 inline 索取**：把該 URL 記入「缺 Axure access code」清單，**不停下、繼續跑下一個 URL**
- 底層 extractor 行為（cache miss 且 access code 齊備時觸發）：
    1. 以 SHA-512 hash access code，POST 到 `/prototype/dologin/<ID>` 取得 auth cookie
    2. 用 cookie 抓取 `data/document.js` 解析 sitemap（頁面列表）
    3. 逐頁抓取 HTML 並抽取文字內容
    4. 輸出 JSON（含頁面結構、文字內容、推測 UI state）
- 其他失敗（access code 錯誤、link 失效、結構異常）→ 記入「其他錯誤」清單，繼續跑
- 若腳本完全無法使用（例如非 axshare.com 格式的 Axure Cloud link）→ 記入「其他錯誤」清單，Step 1.5.3 由使用者決定是否 fallback 為 PDF 匯出 / 截圖 / flow summary 文字

### Step 1.5.3：批次錯誤匯報與補齊

所有 Step 1.5.1 / 1.5.2 的 wrapper 跑完後，**才**彙整成功 / 失敗清單。若無失敗，直接進 Phase 2；若有失敗，依類型分組一次列出：

```
本批抓取結果：成功 N 個 / 失敗 M 個

【缺 Axure access code】3 個 URL：
  - https://abc.axshare.com/#g=1&id=...
  - https://def.axshare.com/#g=1&id=...
  - https://ghi.axshare.com/#g=1&id=...
請貼上對應的 access code（每行一個，順序對應上方 URL；或用「<url>: <code>」格式）。

【Figma token 失效 / 401 / 403】2 個 URL：
  - https://www.figma.com/file/...
  - https://www.figma.com/file/...
請提供新的 Figma token。

【Rate limit (429)】N 個 URL：
  - <url>
處理：等待約 60 秒後自動重跑這批一次（不需使用者操作）；重跑仍 429 才列入本報告，
請使用者決定稍後重試或略過。

【其他錯誤】1 個 URL：
  - https://xyz.axshare.com/... — 結構異常或非 axshare.com 格式
請決定：略過 / 換 fallback（PDF / 截圖 / 文字） / 我要修正 URL。
```

若某 URL 的輸出 JSON 含 `"degraded": true` 或 `page_count` 為 0，視同失敗列入【其他錯誤】組。

收齊使用者補的憑證 / URL 後：

1. rate limit 清單 → 自動重跑一次，僅一次
2. 缺 Axure access code → 對每個 URL 逐一執行 `echo "<code>" | python3 keychain_helper.py axure-store --link "<url>"` 存入 Keychain
3. Figma token 失效 → 執行 `echo "<token>" | python3 keychain_helper.py store` 覆寫 Keychain
4. **只重跑這些缺項 URL**（已成功的不重抓，避免浪費 cache hit）；同樣依序、同樣累積錯誤，必要時再跑一輪 Step 1.5.3
5. 直到所有「使用者堅持要抓」的 URL 都成功，或使用者明確說「這幾個就略過」為止
6. 其他權限問題依 `access-and-credential-handling.md` 處理

## Phase 2: Reconcile

> **模式變體**：
> - **Create mode**：對所有來源做完整 Reconcile。
> - **Update mode（局部模式）**：只對本次菜單觸碰的章節做 Reconcile，未被觸碰的章節保留原文不重寫。`changed_sections` 集合由菜單流程維護，見 `update-mode-menu.md`。
> - **Code Sync mode**：不執行 Phase 2，由 CS-2/CS-3 取代。

1. 從 Axure（讀取 `.ai-artifacts/feature-spec-builder/<feature>/axure/*.json`，或使用者提供的匯出資料）抽流程、入口、分支、例外。
2. 從 Figma（讀取 `.ai-artifacts/feature-spec-builder/<feature>/figma/*.json` 內所有 link 的 frame 列表與文字內容）抽畫面、狀態、元件責任、非 happy path。
3. 從 API / 使用者說明抽 input/output、資料限制、未定 contract。**若有多份 API 文件，逐份比對並合併至🔌 API 規格與附錄 A.2，欄位定義以最新一份為準，並於衝突時列入待確認。**
4. 若有 code path，補 current behavior、既有 state、與改版 impact。
5. 標記：
    - 已確認內容
    - 待確認內容
    - 衝突內容
6. 衝突不在此階段追問。依 Source-of-truth hierarchy（見 SKILL.md）對每個衝突取預設值繼續 compose，並同時：章節內標 `[Conflict]`、列入 Pending Summary 與❓待確認事項。所有衝突問題統一由 Phase 3.5 Step 3 一次向使用者確認。

## Phase 3: Compose

> **模式變體**：
> - **Create mode**：依完整章節順序產出全新 `FEATURE-SPEC.md`。
> - **Update mode（局部模式）**：**只覆寫 `changed_sections` 集合內的章節**，未動章節保留原文（連同既有 `實作位置` 等已回填內容）。文件頭部更新 `Last Updated:`，附錄 C Change Log 追加一筆。
> - **Code Sync mode**：不執行 Phase 3，由 CS-4 直接寫回。

輸出 `FEATURE-SPEC.md`，固定章節順序如下。章節標題使用中文 + 圖示，不使用編號。

**━━━ Human Zone（人類快讀區）━━━**

- Document Status（文件頂部 header metadata，含
  `Structure: Human Zone (摘要 → 驗收條件) | AI Zone (附錄 A～C)`）
- 📋 摘要（必備：功能簡介 → 這次改了什麼 → 使用者主路徑 → 前端負責 vs 不負責 → 影響範圍）
- Pending Summary（僅有 pending 時出現，放在📋摘要之後）
- 🎯 目標與範圍（業務目標、使用者價值、不包含範圍）
- 🔄 核心流程（頁面清單表格 + Mermaid 主流程圖 + 替代流程與失敗處理）
- 📐 業務規則（規則表含「實作位置」欄位，初始 TBD）
- 📱 畫面規格（每畫面：用途 → 資料來源 → 狀態表 → 使用者操作 → 元件細節 → 錯誤處理）
- 🔌 API 規格（每支 API：用途、呼叫時機、Request、前端使用/不使用的欄位）
- 🛠️ 程式影響範圍（新增/更新/共用檔案 + DI/快取/導頁 + 技術備註）
- ✅ 驗收條件（正常路徑 + 邊界情境 + 失敗情境，Given-When-Then 格式）
- ❓ 待確認事項（僅有待確認時出現）

（Human Zone 結束後加入分界線：`---` +
`> **AI Reference Zone** — 以下附錄為結構化工程資料，主要供 AI Agent 與深度查找使用。各欄位使用方式見上方🔌 API 規格章節。` +
`---`）

**━━━ AI Reference Zone（AI 查找區）━━━**

- 附錄 A：型別定義與欄位對應（A.1 舊→新對應、A.2 完整型別 pseudo-code、A.3 Enum 對應、A.4 Analytics 事件）
- 附錄 B：歷史與遷移參考（已廢棄的舊邏輯，僅改版功能需要）
- 附錄 C：參考資料與變更紀錄（來源連結 + 表格格式 Change Log）

> **⚠️ Phase 3 出口 — DO NOT STOP**：寫出 `FEATURE-SPEC.md` 後，**絕對不要停下、不要回報「spec 已完成」、不要等待使用者指示**。此檔目前只是草稿，skill 尚未結束。**立即接續下方 Phase 3.5**（其 Step 0 會先輸出一行可見宣告）。這是本 skill 最常見的斷流點（Codex 等 harness 尤甚），違反此規則等於沒有完成 skill。
>
> 注意：「不可停」**不適用於 Phase 3.5 Step 3** —— 該處有問題清單時**必須停下等待使用者**；跳過提問直衝 Phase 4 與中途棄跑同樣是違規。

## Phase 3.5: Post-Draft Q&A（強制蒸餾輪次）

依 `post-draft-qa-checklist.md` 執行內部審查與問答。此步驟為強制執行，**此階段可一次列出所有問題，不受
Phase 1 逐一提問規則限制**。

**Q&A Gate（硬規則摘要，完整定義見 checklist 檔首）**：

- 草稿含 `[Pending]` / `[Needs confirmation]` / 非空 `Pending Summary` / 非空 `❓ 待確認事項` / 未經確認的模型推論 → **必須**輸出 Step 3 問題清單並停下等待使用者。**把 pending 寫進 spec ≠ Phase 3.5 通過。**
- 進入 Phase 4 前必須輸出一行 gate disposition（對使用者可見）：`PASS_NO_QUESTIONS`（Step 1 全過且 Pending Scan 命中 0）/ `PASS_USER_CONFIRMED`（已問、已逐項回覆）/ `PASS_USER_CONTINUE`（已問、使用者說「繼續」）。沒有 disposition 不得進 Phase 4。

## Phase 4: Validate

在輸出前檢查：

- 是否明確標示文件狀態與 `Structure: Human Zone (摘要 → 驗收條件) | AI Zone (附錄 A～C)`
- 📋 摘要是否先說「功能簡介」（這功能是什麼），再說「這次改了什麼」
- 📋 摘要是否包含「前端負責 vs 不負責」表格
- 🔄 核心流程是否有頁面清單表格（在 Mermaid 圖之前）
- 🔄 核心流程是否有 Mermaid 主流程圖
- 📐 業務規則的每張規則表是否都有「實作位置」欄位
- 📱 畫面規格每個畫面是否都有狀態表
- 🔌 API 規格是否明確區分「前端使用」與「前端不使用」的欄位
- ✅ 驗收條件是否分為正常路徑 / 邊界情境 / 失敗情境
- 附錄 C 的變更紀錄是否為表格格式
- **Single Source of Truth**：同一欄位的行為邏輯是否只在一個章節完整定義（不在多處重複展開）
- API 未定時是否明顯標示 pending
- 衝突是否已追問或保留 pending
- 是否把推論偽裝成既定規格
- 是否符合固定章節順序（Human Zone 在前，AI Zone 附錄在後）
- Phase 3.5 gate disposition 是否已輸出且為 `PASS_NO_QUESTIONS` / `PASS_USER_CONFIRMED` / `PASS_USER_CONTINUE` 三值之一？若草稿含 pending 而 disposition 為 `PASS_NO_QUESTIONS` → gate 違規，**退回 Phase 3.5**
- 未解決問題是否已加入❓待確認事項
