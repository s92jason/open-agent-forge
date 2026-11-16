---
name: smart-commit-flow
description: 產生推薦 commit message、幫我 commit、確認後再 push；可用 /smart-commit-flow 直接觸發並帶參數偏好（例如 no-push、fix(ui)、short）
allowed-tools: Bash(git:*) Bash(python3:*)
metadata:
  argument-hint: "[偏好/限制，例如 no-push | fix(ui) | short | zh]"
  user-invocable: "true"
---

# Smart Commit Flow

> 這個 Skill 目標：**先分析 staged diff → 產生 3 個最適合的 commit message → 你選擇/重生/自填/放棄 → 列出完整 commit 資訊 → 你確認後才 commit → 再問要不要 push**。  
> 你也可以用指令直接觸發：`/smart-commit-flow $ARGUMENTS`

## Direct invocation（指令觸發）
- 使用者輸入 `/smart-commit-flow ...` 時，**強制啟動**本 Skill。
- `$ARGUMENTS` 視為「偏好/限制」，用來影響本次候選訊息與流程，不需要非常嚴格解析，但要盡量尊重使用者意圖。
- 常見參數（自由文字也可）：
  - `no-push`：commit 後不要進入 push 步驟
  - `push`：commit 後希望進入 push 步驟（仍要 push 前確認）
  - `short` / `更短`：候選訊息偏短、資訊密度高
  - `en` / `英文`：候選訊息改用英文（預設為繁體中文）
  - `fix(...)` / `feat(...)` / `refactor(...)`：希望優先使用指定 type/scope（若不合理要說明原因並給替代）

> 若你想讓它「只能指令觸發、避免自動誤觸發」，可在 frontmatter 加上：`disable-model-invocation: true`。

---

## Trigger cues（該啟用）
- 「幫我產生 commit message」
- 「幫我 commit / 提交」
- 「幫我 commit 並 push / 確認後 push」
- 「依照 git diff 推薦 commit 訊息」
- 使用者貼出 diff 並要求生成 commit message

## Non-trigger cues（不該啟用）
- 只是問 Git 概念/教學、沒有要 commit/push
- Repo 不是 Git 倉庫（`git rev-parse --is-inside-work-tree` 失敗）→ 轉 troubleshooting

---

## Operating procedure（流程）

### 成功標準（你要以此自我檢查）
- 候選訊息：**三個都符合規範、使用繁體中文**、差異明確（保守/偏產品/偏工程），且確實對應 staged diff
- 流程簡潔：選擇候選後直接 commit，**不需額外確認**；只在 push 前確認
- 安全性：push 前必須列出檔案變更摘要並取得使用者明確同意
- 可追溯：commit 後輸出 sha、branch、message
- 可回復：commit/push 卡關時能分類問題、提供可執行的修復路徑

---

### Step 0 — 建立 Git Context Bundle（必做）
在 repo root 執行：
- `python3 scripts/build_commit_bundle.py`

生成後讀取：
- `.ai-artifacts/smart-commit-flow/commit_bundle.md`
- `.ai-artifacts/smart-commit-flow/commit_bundle.json`

若生成失敗 → 讀 `references/troubleshooting.md` 的「Bundle 生成失敗」。

---

### Step 1 — 決定 commit 範圍（staged vs unstaged）
規則（硬性）：
- **只針對 staged 內容產生候選 commit message**
- 若 staged 為空但有 unstaged：先詢問是否要 stage（詢問時用 `(y/n)` 格式）
  - 推薦：`git add -p`
  - 或指定路徑：`git add <paths>`
  - 或放棄（不 commit）

---

### Step 2 — 讀規範並產生 3 個候選 commit message（必做）
必讀：`references/commit-message-standard.md`

產生三個候選，每個都要符合：
- header：`<type>(<scope>): <subject>`
- body/footer：必要時才加（複雜原因、breaking、票號等），並遵守 72 字換行
- **預設使用繁體中文**（除非使用者指定 `en` 參數）

候選定位要求：
- 候選 A：最精準、最保守（最貼近 diff）
- 候選 B：偏使用者/產品語意（從使用者價值描述）
- 候選 C：偏工程語意（refactor/perf/build/ci 等）

---

### Step 3 — 讓使用者選擇（必做）
用清楚選單呈現，**候選訊息直接寫在選項中**方便閱讀：
- [1] `feat(scope): 候選 A 的完整訊息`
- [2] `feat(scope): 候選 B 的完整訊息`
- [3] `refactor(scope): 候選 C 的完整訊息`
- [R] 重新產生（可依 $ARGUMENTS 或使用者回饋調整：更短/更具體/換 type/scope）
- [I] 自己輸入（你要做格式檢查與修正建議）
- [A] 放棄（不 commit）

---

### Step 4 — 選擇後直接執行 commit（不需再確認）
使用者選擇候選訊息後，**直接執行 commit，不需額外確認**。

執行 commit（視訊息是否多段）：
- 單段：`git commit -m "<header>"`
- 多段：`git commit -m "<header>" -m "<body>" -m "<footer>"`

commit 成功後，簡短列出：
- commit sha
- commit message
- branch

若 commit 失敗：
- 讀 `references/troubleshooting.md` 的「Commit 失敗」
- 先分類原因，再給出可執行修復步驟
- 任何修復動作若會改狀態 → 仍要先列命令並確認

---

### Step 5 — push 前確認（必做，包含變更摘要）
- 若 `$ARGUMENTS` 包含 `no-push`：跳過 push，但仍列出「你可以手動 push 的命令建議」
- 其他情況：詢問是否 push，**確認畫面必須包含並按照以下順序**：
  - 將 push 到哪（remote/upstream）
  - 若無 upstream，建議 `git push -u origin <branch>`
  - **檔案變更內容摘要**（說明每個檔案改了什麼，不只是行數）
  - commit message
  - 詢問「是否 push？(y/n)」

push 後顯示結果；失敗則按 troubleshooting 提供解法。

---

### Step 6 — 提出建議或問題（可選、先確認）
根據 diff / 候選訊息提出可行建議（先問要不要加）：
- 是否應拆成多筆 commit（指出分組依據）
- scope 是否可更精準
- 是否需要票號/issue id（若專案有慣例；不得憑空捏造）
若使用者希望整合到 commit message：可走 `git commit --amend`（再次列命令並確認）。

---

## Output contract（輸出格式保證）
- 候選訊息使用**繁體中文**（除非使用者指定 `en`）
- 候選訊息**直接寫在選項中**，格式：`[1] feat(scope): 完整訊息`
- 選擇候選後**直接 commit**，不需額外確認
- **push 前必須確認**，確認畫面包含：檔案變更內容摘要（說明改了什麼）、commit message、push 目標
- 是/否的詢問一律使用 `(y/n)` 格式
- diff 過長時：聊天只顯示摘要與關鍵片段，完整內容以 `.ai-artifacts/smart-commit-flow/commit_bundle.md` 為準

---

## Progressive disclosure map（何時讀/跑什麼）
- 一開始必跑：`scripts/build_commit_bundle.py`
- 產生/檢查 commit message 前必讀：`references/commit-message-standard.md`
- 遇到錯誤才讀：`references/troubleshooting.md`
- 需要範例/對照讀：`references/templates/commit-message-examples.md`
- 需要自檢清單讀：`references/templates/commit-message-checklist.md`
