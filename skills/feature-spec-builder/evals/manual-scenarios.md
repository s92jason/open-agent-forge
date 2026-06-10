# Feature Spec Builder Manual Scenarios

這份清單用來手動回歸 Phase 3.5 Q&A Gate。情境寫法不依賴特定 agent 或 harness；在 Codex、Claude Code、Antigravity 或其他可執行本 skill 的環境中皆可照同樣步驟驗證。

## Scenario 1: 陷阱題 - 有設計連結但沒有 API 文件

### 前置輸入

- Mode: Create
- 提供至少 1 個 Axure 或 Figma 設計連結
- 明確告知：「API 文件目前沒有」
- 需求描述包含一個需要 API 欄位才能定稿的畫面或狀態，例如列表資料、empty state 或 error handling

### 操作步驟

1. 依 Create mode 啟動 feature-spec-builder。
2. 在 intake 階段貼上設計連結，API 文件詢問時回答「目前沒有」。
3. 允許 skill 產生草稿並進入 Phase 3.5。
4. 當 Phase 3.5 輸出問題清單時，回覆「繼續」。

### 必須觀察到的錨點輸出

- Step 0 宣告行：`草稿已產出，正在執行 Phase 3.5 內部審查`
- Step 3 問題清單，且問題清單輸出後停下等待使用者回覆
- 使用者回覆「繼續」後，輸出 `Phase 3.5 gate: PASS_USER_CONTINUE`
- 草稿中缺 API 定義處保留 `[Pending]`，且對應 `Pending Summary` 與 `❓ 待確認事項`

### PASS 判定

- PASS: 依序觀察到所有錨點輸出，且全程沒有在 gate disposition 之前宣告「完成」。
- FAIL: 跳過提問直接進 Phase 4，或在 disposition 之前宣告「完成」。這明確對應 v1.17.2 的失誤路徑。

## Scenario 2: 乾淨案例 - 所有來源齊備且無衝突

### 前置輸入

- Mode: Create
- 提供完整 Axure flow、Figma key frames、API 文件與必要補充說明
- 來源之間沒有互相衝突，且 API 欄位足以支撐所有 UI state 與流程

### 操作步驟

1. 依 Create mode 啟動 feature-spec-builder。
2. 依序提供 Axure、Figma、API 文件與補充說明。
3. 允許 skill 完成 Phase 2 reconcile、Phase 3 compose 與 Phase 3.5 gate。

### 必須觀察到的錨點輸出

- Step 1.5 Pending Scan 的掃描證據，命中數為 0
- `Phase 3.5 gate: PASS_NO_QUESTIONS`
- 沒有輸出 Step 3 問題清單
- 最終草稿不包含 `[Pending]`、`[Conflict]`、`[Needs confirmation]`、`[Source not provided]` 或 `Pending API confirmation`

### PASS 判定

- PASS: Step 1.5 掃描證據命中 0，輸出 `PASS_NO_QUESTIONS`，且不向使用者提問。
- FAIL: 在命中 0 的乾淨案例仍提問，或未輸出 gate disposition 就進 Phase 4。

## Scenario 3: Update 局部案例 - 未觸碰章節保留舊 pending

### 前置輸入

- Mode: Update
- 既有 `FEATURE-SPEC.md` 的未觸碰章節留有舊 `[Pending]`
- 本次菜單只選 API 相關更新，例如選項 C
- 本次只修改 🔌 API 規格，且新增或修改內容沒有新的 pending

### 操作步驟

1. 依 Update mode 啟動 feature-spec-builder。
2. 只選 API 相關菜單項目，提供足夠 API 資料完成本次修改。
3. 完成草稿後執行 Phase 3.5 Step 1.5 Pending Scan。
4. 檢查 scan 證據只統計 `changed_sections` 對應章節。

### 必須觀察到的錨點輸出

- Step 1.5 掃描證據包含章節與行號，例如 `🔌 API 規格（行號）`
- 未觸碰章節的舊 `[Pending]` 不被計入本次命中數
- 本次 `changed_sections` 範圍命中數為 0
- `Phase 3.5 gate: PASS_NO_QUESTIONS`，並告知未變更章節維持原狀

### PASS 判定

- PASS: 舊 pending 不觸發提問，changed_sections 範圍規則生效，且 disposition 正確。
- FAIL: 未觸碰章節的舊 pending 觸發提問，或沒有提供章節/行號證據。
