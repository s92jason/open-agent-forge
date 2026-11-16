---
name: branch-diff-code-review
description: 幫我 review 這條分支 / review branch / 依分支起點到 HEAD 的 diff 做 Code Review，支援自動分 chunk 與 100 分評分
---

# Branch Diff Code Review Skill

## Trigger cues
當使用者出現以下意圖，啟用本 Skill：
- 「幫我 review 這條分支」
- 「針對目前分支做 code review」
- 「從分支起點到 HEAD 的 diff 做 review」
- 「幫我看這次分支改動品質，給評分」
- 「變更太多，請自動切 chunks 逐段 review」

## Non-trigger cues
以下情境不要啟用（改用一般問答或 PR review skill）：
- 只問單一檔案/單一函式怎麼寫（不需要 branch diff）
- 想 review 已經合併的 PR（應以 PR/commit 範圍為準）
- 使用者沒有在 git repo 內，或沒有可用的 git 指令環境
- 使用者只想要格式化/重構建議而不是針對改動範圍評估

---

## Operating procedure

### Step 0 — Safety / scope guard
1. 僅處理「目前 git repo」且「目前分支」的變更；不掃整個 repo 的所有檔案。
2. 忽略二進位檔、lock 檔、產物檔（可由 `references/review-checklist.md` 的「排除清單」判斷），除非使用者明確要求審查。
3. 若偵測到疑似秘密（API key、token、private key）出現在 diff，立刻在報告中標紅高風險提醒，並避免在輸出中完整重印敏感內容（只描述位置與型態）。

### Step 1 — 找出分支起點（branch point）【Local-only / 禁用 origin/*】
1. 僅允許本地 base：
   - 自動候選：`main`, `master`, `develop`
   - 或使用者指定：`BASE_REF=<local-branch-or-tag>`、`BASE_COMMIT=<sha>`
2. 嚴格禁止使用任何 remote-tracking refs：
   - 禁止：`origin/*`, `refs/remotes/*`, `upstream/*`
   - 禁止任何網路操作：`git fetch/pull/push/ls-remote/clone`
3. base commit 計算：
   - 若有 `BASE_COMMIT`：直接用它
   - 否則：`git merge-base <current-branch> <BASE_REF or local default>`

### Step 2 — 產生 Review Bundle（含自動 chunking）
1. 執行 `scripts/build_review_bundle.py`：
   - 取得改動檔案清單（added/modified/renamed/deleted）
   - 對每個文字檔案擷取：
     - base 版本全文（若存在）
     - head 版本全文（若存在）
     - unified diff（含行號）
   - 預估 token 量（粗估：字元/4）並決定是否 chunk
2. chunk 策略：
   - 預設上限 `MAX_TOKENS=12000`（可用 env 覆蓋）
   - 超過就依 `references/chunking.md` 的規則自動分組（以 Gradle module / 目錄 / package / feature 命名等）
3. 產出資料夾：`.ai-artifacts/branch-diff-code-review/`
   - `manifest.json`（range、base、head、檔案統計、chunk 列表）
   - `chunks/chunk-01.md`, `chunk-02.md`, ...
   - `all-in-one.md`（若未超過 token 上限）

### Step 2.5 — Cache 檢查（同 HEAD 自動沿用上次 review）

build bundle 完成後，立刻檢查 cache：

```bash
python3 "$SKILL_DIR/scripts/review_cache.py" check
```

stdout 是 JSON，含 `hit: bool` 與 `reason: str`：

- `hit=true` → 跳過下方 Step 3、Step 4，改走「Cache HIT 路徑」：
  1. 讀 `.ai-artifacts/branch-diff-code-review/review-output.md`
  2. 在輸出開頭印一行透明告知：
     ```
     本次使用 cache 自 <saved_at>（HEAD `<head_commit>` / base `<base_commit>` 未變動，rule files 未變）。
     如需重跑，請執行：rm -rf .ai-artifacts/branch-diff-code-review/
     ```
  3. 把 review-output.md 內容呈現給使用者，**流程結束**
- `hit=false` → 繼續往下走 Step 3 / Step 4 正常流程

**沒有對話 bust 指令**（依專案 CLAUDE.md Cache 化原則第 3 條）：使用者要強制重跑就 `rm -rf` bundle 資料夾。Rule files（SKILL.md / scoring-rubric.md / review-checklist.md / chunking.md / business-logic-heuristics.md）任一變更會自動 invalidate cache。

### Step 3 — 逐 chunk Review
1. 依序讀取 chunk 檔（從 chunk-01 開始）
2. 對每個 chunk 產生「chunk review」輸出，格式必須符合 `references/templates/chunk-review-template.md`
3. 每個 chunk review 需包含：
   - 重大問題（阻擋合併 / 高風險）
   - 一般建議（可讀性、架構、測試、效能）
   - 商業邏輯/產品行為建議（見 `references/business-logic-heuristics.md`）
   - 檔案級建議（按檔案列點，能對應到 diff 行號）

### Step 4 — 彙總總報告 + 100 分評分
1. 讀取所有 chunk review 的結論，合併去重、整理優先序（P0/P1/P2）
2. 用 `references/scoring-rubric.md` 做評分：
   - 必須列出各項得分與扣分理由
   - 總分最高 100 分
3. 最終輸出格式必須符合 `references/templates/review-report-template.md`

### Step 4.5 — Finalize Cache（為下次同 HEAD 沿用做準備）

完成 Step 4 後，**Claude 必須執行**以下兩個動作（除非本輪是 Cache HIT 路徑，HIT 路徑跳過此步驟）：

1. 用 `Write` 工具把**最終整份 review 報告**寫到 `.ai-artifacts/branch-diff-code-review/review-output.md`（內容與輸出給使用者的完全一致）。
2. 執行 `python3 "$SKILL_DIR/scripts/review_cache.py" finalize`，把 review 的 sha256、rules_hash、base/head 寫入 `cache.json`。

下次同 HEAD 跑 skill 時，Step 2.5 會偵測到並自動沿用。

---

## Output contract（輸出契約）
最終輸出必須包含以下段落（缺一視為不合格）：
1. Review 範圍：base-ref、base-commit、HEAD、檔案數、diff 統計
2. Executive summary（3–8 句）
3. P0 / P1 / P2 問題清單（每點要可行動、可驗證）
4. 逐檔案建議（含 diff 行號/區塊定位；避免空泛）
5. 商業邏輯/產品建議（行為/風險/邊界條件/監控）
6. 測試建議（缺口、可加的測試類型與範例）
7. 評分表（拆項加總到 100）+ 扣分依據
8. 假設與限制（例如 base 推斷方式、跳過檔案、內容截斷）

---

## Progressive disclosure map
- 需要如何分 chunk → 讀 `references/chunking.md`
- 需要完整檢查清單與排除規則 → 讀 `references/review-checklist.md`
- 需要商業邏輯建議角度 → 讀 `references/business-logic-heuristics.md`
- 需要評分規則與扣分準則 → 讀 `references/scoring-rubric.md`
- 需要固定輸出格式 → 讀 `references/templates/*`

---

## Tooling（在 Claude Code 中）
- 允許使用：git、python3
- 建議流程（在 repo 根目錄執行）：
  1) `SKILL_DIR="$HOME/.claude/skills/branch-diff-code-review"`
  2) `python3 "$SKILL_DIR/scripts/build_review_bundle.py"`（一律執行，bundle 重生很便宜）
  3) `python3 "$SKILL_DIR/scripts/review_cache.py" check` — 解析 stdout JSON：
     - `hit=true` → 讀 `.ai-artifacts/branch-diff-code-review/review-output.md`，加上透明告知後輸出給使用者，流程結束
     - `hit=false` → 繼續下方 4–6
  4) 讀 `.ai-artifacts/branch-diff-code-review/manifest.json` 確認 range 與 chunk 數量
  5) 依序讀 `.ai-artifacts/branch-diff-code-review/chunks/chunk-01.md`、`chunk-02.md`… 逐段 review
     - 若 `all-in-one` 欄位非 null，可改讀 `.ai-artifacts/branch-diff-code-review/all-in-one.md` 一次完成
  6) 完成總報告後，用 `Write` 工具把最終 review 寫到 `.ai-artifacts/branch-diff-code-review/review-output.md`，
     然後 `python3 "$SKILL_DIR/scripts/review_cache.py" finalize` 寫 cache.json
- 可用 env 覆蓋：`MAX_TOKENS=8000`（縮小 chunk）、`BASE_REF=feature/xxx`（指定 base）、`BUNDLE_DIR=...`（自訂輸出位置；`review_cache.py` 也吃此變數）
- 強制重跑：`rm -rf <repo>/.ai-artifacts/branch-diff-code-review/`（同時 reset bundle 與 cache，沒有專屬對話指令）
