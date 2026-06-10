---
name: feature-spec-builder
description: 當使用者說「幫我根據 Axure 和 Figma 產 feature spec」「更新 FEATURE-SPEC.md」「依改版補工程規格文件」「幫我把 spec 對齊 code」「依目前程式碼同步 spec」「feature 收尾要對 spec」，或在英文說 "build/update a FEATURE-SPEC.md from Axure/Figma", "generate an engineering feature spec for RD/QA", "sync the spec to the current code" 時，建立、更新或同步以 RD/QA/AI 可共讀的 engineering feature spec。Supports three modes — Create / Update (menu-driven) / Code Sync（程式碼反向同步）。
keywords: [feature spec, 工程規格, 規格文件, FEATURE-SPEC, Axure, Figma, spec 對齊, code sync, 同步 spec, engineering spec, RD spec, QA spec]
---

# Engineering Feature Spec Builder

## Core Principles

第一準則：讓人類工程師在 5~10 分鐘內快速建立正確認知。spec 是活文件，可持續滾動調整。
第二準則：讓 AI Agent 可直接把 spec 當後續 SDD task / validation 的核心 artifact。
第三準則：**Single Source of Truth per dimension** — 每條規則只在一個章節完整定義，其他章節只引用，不重複展開。

- 欄位定義 → 只在🔌 API 規格完整列出
- 欄位對 UI 的影響 → 只在📐業務規則或📱畫面規格完整描述
- 欄位在流程中的角色 → 只在🔄核心流程用 Mermaid 圖表達
- 其他章節需要引用時，用一行摘要 + 「見📐業務規則」等指引，不重寫完整邏輯

FEATURE-SPEC.md 分為兩區：**Human Zone**（人類快讀）在前，**AI Reference Zone**（結構化查找）在後。文件開頭標示
`Structure:` 讓讀者一眼識別文件架構。

## Purpose

把 Axure + Figma 為核心的設計與需求資訊，整理成 repo 內單一真相來源的 `FEATURE-SPEC.md`。
輸出文件主要給 RD、QA 與 AI Agent 使用，不承擔 PM/PRD 的產品敘事責任。

## Trigger cues

當使用者明確要你：

- 根據 Axure 與 Figma 產出 `FEATURE-SPEC.md`
- 建立新功能的 engineering feature spec
- 根據改版設計更新既有 `FEATURE-SPEC.md`
- 將 Axure / Figma / API / 補充需求整理成工程規格文件
- 依這次 backlog 設計頁面蒸餾成 repo 內規格
- **feature 收尾時把 spec 對齊目前程式碼**（Code Sync mode）

常見說法：

- 幫我根據 Axure 和 Figma 產 feature spec
- 幫我更新這個功能的 `FEATURE-SPEC.md`
- 幫我把這次改版整理成工程規格文件
- 幫我依設計稿補一份 RD 用的 spec
- 這個功能要建 canonical feature spec
- 幫我把 spec 對齊 code
- 依目前程式碼同步 spec
- feature 收尾要對 spec
- sync spec from code

## Non-trigger cues

以下情況不要啟用：

- 只想做 PRD / PM 文件 / 商業敘事
- 只想做 code review / spec gap review，不需要產完整 spec
- 只有零碎想法，尚未有 Axure 與 Figma
- 純 bug fix、純 refactor、純 commit message
- 只想問某段程式碼邏輯，沒有要建立或更新 `FEATURE-SPEC.md`

## Source-of-truth hierarchy

遇到衝突時，最高優先永遠是：

1. 使用者明確確認的需求與範圍
2. API contract / backend reality

其餘依衝突面向決定：

| 衝突面向                     | 優先順序                          |
|--------------------------|-------------------------------|
| 互動流程（entry、分支、back flow） | Axure > Figma > 現有 code       |
| 視覺與狀態（畫面、元件、state）       | Figma > Axure > 現有 code       |
| 資料契約（欄位、格式、錯誤碼）          | API > 現有 code > Axure / Figma |

最後才是模型推論，且必須標注為推論。

規則：

- 不可默默用低優先來源覆蓋高優先來源。
- 發現衝突時，依上表 hierarchy 取預設值繼續，標記 [Conflict]，於 Phase 3.5 集中向使用者確認。
- 若 Phase 3.5 仍無法確認，文件內保留 pending，不可假裝定稿。

## Minimum source gate

正式產出 spec 前，至少需要一個設計來源：

- Axure link 或 Figma link（至少其一）

若兩者都缺：

- 不直接產正式 spec
- 明確告知來源不足
- 只可在使用者確認接受的前提下輸出骨架草稿，且標記為 `Status: Draft`

若只有其中一個：

- 可產出 spec，但缺少的來源對應章節標記 `[Source not provided]`
- 文件狀態至多為 `In Progress`，不可標為 `Ready`

## Modes

### Create mode

適用於：

- 尚無 `FEATURE-SPEC.md`
- 使用者明確要求新建 spec

Create mode 依 `references/operating-procedure.md` Phase 1 Step 3 ~ Step 6.1 的順序式 intake 收集 Feature Name、目錄、Axure、Figma、API 文件（**API 文件支援多輪收集**，與 Axure / Figma 一致，沿用「完成 / 沒了 / done」終止語）。

### Update mode

適用於：

- 已存在 `FEATURE-SPEC.md`
- 使用者明確要求更新
- 或你已檢查到現有 spec 檔案

Update mode 採**菜單式流程**（不再沿用 Create mode 的順序式 intake）：

1. 先讀取既有 `FEATURE-SPEC.md`，從 `# Feature Spec: <Name>` header 萃取 Feature Name，**不再重問名稱**。若檔頭缺漏才 fallback 詢問。
2. 顯示偵測到的 spec 摘要（Status / Last Updated / 待確認事項數量 / 章節索引）。
3. 顯示菜單供使用者挑選本次要動的面向：
   - A. Axure 補充 / 修改
   - B. Figma 補充 / 修改
   - C. API 規格補充 / 修改
   - D. 回答待確認事項
   - E. 自行補充事項
   - F. 現行程式碼局部同步（共用 Code Sync 引擎，scope 限縮於使用者指定路徑）
   - G. 其他（自行描述）
   - H. 結束並進入 Reconcile
4. 每執行完 A–G 任一動作，回菜單；使用者選 H 才進入 Phase 2 Reconcile（局部模式，只跑被觸碰章節）。

完整菜單細節、各選項子流程、`changed_sections` 範圍標記規則見 `references/update-mode-menu.md`。

Update 原則：

- 優先更新受影響章節，不暴力整份重寫
- 保留有價值的既有內容（包含已回填的「實作位置」等）
- 於文件頭部和附錄 C `Change Log` 標示本次更新重點

### Code Sync mode（程式碼同步模式）

適用於：

- 已存在 `FEATURE-SPEC.md` 且 feature 即將收尾 / merge / release
- 使用者明確要求「以目前程式碼為事實基礎反向驗證 spec」
- 想自動回填 📐 業務規則「實作位置: TBD」、找出 code 與 spec 的不一致 / 缺漏 / 過時段落

Code Sync mode 採 **CS-1 ~ CS-4 流程**（不與 Phase 1–4 混用）：

1. **CS-1 Intake**：沿用 Update mode 的 read-first 機制萃取 Feature Name；詢問掃描範圍（沿用🛠️ 程式影響範圍清單 / 指定資料夾 / 指定檔案 list）。
2. **CS-2 Code Scan**：純 Read 讀取目標檔案，萃取 API endpoint、欄位、Composable / Fragment、ViewModel state、業務規則對應的 code 位置（初版聚焦 Kotlin / Compose）。
3. **CS-3 Diff Report**：輸出 4 類差異（TBD 回填 / 缺漏項 / 不一致 / 過時段落），標 P0/P1/P2，**read-only，使用者勾選後才寫回**。
4. **CS-4 Apply**：依勾選項目寫回 spec，附錄 C Change Log 追加「程式碼同步更新」，未勾選的 P0 不一致自動轉為 ❓ 待確認事項。

完整流程、Diff Report 表格格式、與 Update menu F 的職責分工見 `references/code-sync-procedure.md`。

> Update mode 的菜單 F 選項與獨立 Code Sync mode **共用同一 CS-2/CS-3 引擎**，差別僅在 scope（局部 vs 全量）。

## Settings management mode

當使用者說「查看 spec 設定」「更新 coding standard」「重設專案設定」等觸發詞時，依
`references/settings-management.md` 處理，不執行 spec 產生。

## Operating procedure

執行前先讀取 `references/operating-procedure.md` 取得完整步驟。

**完成契約（跨 harness 防斷流）**：本 skill 只有跑到 **Phase 4 Validate 通過**才算完成；產出 `FEATURE-SPEC.md` 只是 Phase 3 草稿，**不等於完成**。全程**唯一允許停下交還使用者**的點只有三個：① Phase 1 intake 提問 ② Phase 1.5 補憑證 ③ Phase 3.5 Step 3 問題清單（**有問題時為強制停點，不是可選**）。其餘 phase 之間一律連續執行，**尤其 Phase 3 寫出文件後必須立即接 Phase 3.5，不可停下或回報完成**（這是 Codex 等 harness 最常見的斷流點）。Phase 3.5 結束時必須輸出 gate disposition（`PASS_NO_QUESTIONS` / `PASS_USER_CONFIRMED` / `PASS_USER_CONTINUE`）才能進 Phase 4；草稿含 pending 時 `PASS_NO_QUESTIONS` 不合法（見 `references/post-draft-qa-checklist.md` 的「Q&A Gate」）。

以下為各 phase 摘要：

- **Phase 1: Intake** — 逐一收集 mode、feature name、path、Axure link（多輪）、Figma link（多輪）、API doc（Create mode 必問）、token、設定（一次只問一個問題；Axure/Figma 步驟持續詢問直到使用者說「完成」/「沒了」/「done」）。**資源類問題（Axure / Figma / API）只蒐集不立即抓取**，所有來源收齊後在 Step 9 顯示資源摘要、由使用者明確確認才進入 Phase 1.5。
- **Phase 1.5: Source Extraction** — 透過 `scripts/extract_with_cache.py` wrapper 抽取設計資料，
  每個 link 一份獨立 JSON 在 `.ai-artifacts/feature-spec-builder/<feature>/{figma,axure}/<hash>.json`。
  **統一在 Phase 1 confirm gate 通過後執行批次抓取**：依序對每個 URL 呼叫 wrapper，單個 URL 失敗不阻斷其他 URL，所有 wrapper 跑完才在 Step 1.5.3 一次性匯報缺項與錯誤（缺 Axure access code / Figma token 失效 / URL 異常等），由使用者一次補齊後重跑缺項。
  Wrapper 內建 cache 機制：Create mode 自動沿用 cache、Update menu A/B 必加 `--bust-cache` 強制重抓
  （規則見 `references/cache-policy.md`）。Code Sync mode 不跑此 Phase。
- **Phase 2: Reconcile** — 交叉比對 Axure 流程、Figma 畫面、API contract，標記已確認 / 待確認 / 衝突；衝突不追問，取 hierarchy 預設並標 [Conflict]
- **Phase 3: Compose** — 依固定章節順序輸出 `FEATURE-SPEC.md`（Human Zone 📋→✅ → AI Zone 附錄 A–C）。**寫檔後不可停、不可回報完成，立即接 Phase 3.5**
- **Phase 3.5: Post-Draft Q&A** — 先輸出一行可見宣告（Step 0）再依 `references/post-draft-qa-checklist.md` 強制執行內部審查，此階段可一次列出所有問題。結束時必須輸出 gate disposition；**把 pending 寫進 spec 不等於通過此 phase**
- **Phase 4: Validate** — 輸出前逐項檢查文件完整性與正確性

## Output contract

### Header requirements

文件開頭必須包含：

- `# Feature Spec: <Feature Name>`
- `Status: <Draft / Pending API confirmation / In Progress / Ready>`
- `Last Updated: <date>`
- `Mode: <Create / Update / Code Sync>`
- `Structure: Human Zone (摘要 → 驗收條件) | AI Zone (附錄 A～C)`

若有待補，文件頭部必須加：

- `Pending Summary`（放在📋摘要之後）

### Chapter requirements

章節標題使用中文 + 圖示，不使用編號。

**Human Zone 章節（工程師快讀）**

- `📋 摘要`：
    - **功能簡介**（必備）：先說這個功能「是什麼」、「幹嘛用的」，讓第一次接手的人在前 3 行就知道功能目的
    - **這次改了什麼**：一段話說明本次改版重點
    - **使用者主路徑**：一行描述 happy path
    - **前端負責 vs 不負責**：表格，清楚劃出前端邊界
    - **影響的 API / 模組 / 畫面**：條列清單
- `🎯 目標與範圍`：業務目標、使用者價值、不包含範圍（Out of Scope）
- `🔄 核心流程`：
    - **頁面清單**（必備）：表格列出所有頁面名稱、說明、進入方式。即使 Mermaid 無法渲染，工程師也能從此表掌握功能涵蓋的畫面
    - **主流程圖**：至少一個 Mermaid `flowchart TD`
    - **替代流程與失敗處理**：精要版 bullet list（不重述 Mermaid 圖已表達的主路徑）
- `📐 業務規則`：
    - 依規則類型分子節（如方案切換規則、CTA 規則、popup 規則等）
    - 每張規則表必須包含「**實作位置**」欄位（初始為 `TBD`，功能完成後回填檔案路徑）
    - 這是跨章節引用的核心：其他章節提到同一規則時，用「見📐業務規則」指引，不重寫
- `📱 畫面規格`：
    - 每個畫面一個完整區塊，依序包含：用途 → 資料來源 → 狀態表 → 使用者操作 → 元件細節 → 錯誤處理
    - 資料來源只寫 API 名稱 + 頂層物件，不展開完整欄位定義（完整定義在🔌 API 規格）
    - 使用者操作涉及業務規則時，引用📐業務規則，不重寫
- `🔌 API 規格`：
    - 每支 API 獨立子節，包含：用途、呼叫時機、Request、**前端使用的回傳欄位**、**前端不使用的欄位**
      （含原因）、備註
    - 這是欄位定義的唯一完整來源；其他章節引用時只寫欄位名稱
    - 完整型別定義（pseudo-code）放在附錄 A，主文不列
- `🛠️ 程式影響範圍`：新增/更新/共用的檔案表格 + DI/快取/導頁/技術備註
- `✅ 驗收條件`：分為正常路徑、邊界情境、失敗情境三張表（Given-When-Then 格式）
- `❓ 待確認事項`（條件性）：僅有待確認時出現，取代原本散落各處的 pending 標記

**AI Reference Zone 章節（結構化查找）**

- `附錄 A：型別定義與欄位對應`：
    - A.1 舊欄位 → 新欄位對應表
    - A.2 完整型別定義（pseudo-code，給 AI code generation 用）
    - A.3 Enum / 類型對應表（如 popup 類型）
    - A.4 Analytics 事件表
- `附錄 B：歷史與遷移參考`：已廢棄的舊邏輯（僅供歷史參考）
- `附錄 C：參考資料與變更紀錄`：
    - 參考資料（Axure、Figma、既有 code 路徑等）
    - 變更紀錄（表格格式：日期 | 變更摘要）

### Pending notation

待補資訊必須同時用三層表達：

1. 文件頭部的 `Pending Summary`
2. 章節內的 `[Pending]` 或 `[Needs confirmation]`
3. 文件末尾的 `❓ 待確認事項` 章節（Human Zone 最後一章，集中收斂所有 pending 的完整描述）

### Tone

- 上半部簡潔可快速掃讀
- 下半部偏工程文件、結構化、可查找
- 不使用 PM 式敘事
- 不輸出空泛詞，如「優化體驗」「提升互動感」

## Access and credential policy

- 不使用 repo 內 `.local` 或任何專案內明文 secrets。
- Figma 採使用者層級 access token，優先從安全憑證儲存或環境變數讀取。
- Axure 採 share link 為主；若缺 access code，保存「share link 對應 access code」映射，執行時動態注入。
- 不將 token、access code、或帶 code 的完整 URL 寫入：
    - repo
  - `FEATURE-SPEC.md`
    - change log
    - 一般輸出文字
- 若權限不足，Skill 必須明確指出缺的是：
    - Figma token
    - Figma 檔案權限
    - Axure access code
    - Axure share link 有效性
    - 或 Axure workspace / SSO 限制

## Progressive disclosure map

- 當你要執行 spec 產生流程時，讀 `references/operating-procedure.md`（Phase 1–4 完整步驟）
- **當使用者選 Update mode（既有 spec），讀 `references/update-mode-menu.md`**（菜單式流程，A–H 選項細節）
- **當使用者觸發 Code Sync mode（要把 spec 對齊 code），讀 `references/code-sync-procedure.md`**（CS-1 ~ CS-4 完整步驟與 Diff Report 格式）
- 當你需要確認輸入需求與最低門檻時，讀 `references/input-contract.md`
- 當你需要逐章節寫法與判準時，讀 `references/chapter-rules.md`
- 當你要處理 Figma token / Axure access code / 權限錯誤時，讀
  `references/access-and-credential-handling.md`
- 當你要直接建立新檔骨架時，參考 `references/feature-spec-template.md`
- 當你不確定新功能或改版該怎麼寫時，讀：
    - `references/examples/new-feature-example.md`
    - `references/examples/update-feature-example.md`
- 當你在 Phase 3.5 執行 Post-Draft Q&A 時，讀 `references/post-draft-qa-checklist.md`
- 當使用者要查看或更新專案設定時，讀 `references/settings-management.md`
- 當你要了解 Phase 1.5 的 cache 規則（hit 判定七項、Update menu A/B 例外 `--bust-cache`、檔案結構、各模式分流）時，
  讀 `references/cache-policy.md`
- **腳本路徑約定**：下方所有 `scripts/...` 都是相對於本 skill 安裝目錄的捷徑。skill 安裝位置因 harness 而異（Claude plugins 目錄 / Codex skills 目錄 / antigravity workspace），**不可假設 cwd 是 skill 目錄**。執行任何腳本前，先把這份 `SKILL.md` 的所在目錄當作 `<skill-dir>`，用絕對路徑 `<skill-dir>/scripts/<script>.py` 呼叫（詳見 `operating-procedure.md` Step 1.5.0）。
- 當需要管理 Figma token 時，使用 `scripts/keychain_helper.py`：
    - 存入：`echo "<token>" | python3 scripts/keychain_helper.py store`
    - 檢查：`python3 scripts/keychain_helper.py check`（exit 0=有，exit 1=無）
    - 刪除：`python3 scripts/keychain_helper.py delete`
- 當需要管理 Axure access code 時：
    - 存入：`echo "<code>" | python3 scripts/keychain_helper.py axure-store --link "<share_link>"`
    - 取得：`python3 scripts/keychain_helper.py axure-get --link "<share_link>"`
    - 檢查：`python3 scripts/keychain_helper.py axure-check --link "<share_link>"`（exit 0=有，exit
      1=無）
    - 刪除：`python3 scripts/keychain_helper.py axure-delete --link "<share_link>"`
- 當使用者已提供功能名稱與目錄，希望先生成骨架檔案時，可執行：
    -
  `python3 scripts/init_feature_spec.py --feature "<feature-name>" --output "<path>/FEATURE-SPEC.md"`
- 當需要從 Figma / Axure 抽取設計資料時，**一律透過 wrapper 而非直接呼叫底層 extractor**：
    - Figma：`python3 scripts/extract_with_cache.py figma "<figma-url>" --page "<page-name>" --feature-dir <repo-root>/.ai-artifacts/feature-spec-builder/<feature-name>`
    - Axure：`python3 scripts/extract_with_cache.py axure "<axshare-url>" --feature-dir <repo-root>/.ai-artifacts/feature-spec-builder/<feature-name>`
    - **Update menu A / B 路徑下必加 `--bust-cache`**（重列 URL = 使用者明示要 refetch；見 `cache-policy.md`）
    - 輸出位置 = `<feature-dir>/{figma,axure}/<8-char-hash>.json`，hash 由 wrapper 計算
    - Wrapper stdout 印 `CACHE_HIT: <path>` 或 `EXTRACTED: <path>`，直接讀該 path
    - token / access code 由底層 extractor 自動從 Keychain 讀取，wrapper 不接 `--token` / `--code`

## Error handling

- 缺設計來源：停在 intake，明確指出缺口，不假裝完成。
- 來源衝突：取 hierarchy 預設並標 [Conflict]，於 Phase 3.5 集中確認；未確認前不得移除標記。
- API 未定：保留章節，標示 `Pending API confirmation`。
- 只有 Figma file/page link，沒有 key frames：要求補至少 3 個關鍵 frame links。
- Update mode 遇到既有 spec 與新來源不一致：優先保留既有內容並標衝突，不直接刪改。
- Figma / Axure 權限問題：依 `references/access-and-credential-handling.md` 處理。

## Success criteria

好的輸出應該：

- 讓第一次接手的 RD 在 5~10 分鐘內建立正確認知
- 讓 QA 能快速找到主流程與 edge cases
- 讓 AI Agent 可直接把 spec 當後續 task / validation 的核心 artifact
- 對未確認規格有清楚標示，不誤導為已定稿
