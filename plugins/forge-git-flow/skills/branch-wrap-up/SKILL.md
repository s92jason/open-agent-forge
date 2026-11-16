---
name: branch-wrap-up
description: |
  feature branch 收尾一站式流程：TODO 掃描 → 補 docstring（branch-diff-annotator）→ code review（branch-diff-code-review）→ commit（smart-commit-flow）→ PR 草稿。
  review 結果有 P0 問題時自動阻擋 commit；分數低於 70 需明確確認才繼續。
  當使用者說「幫我收尾這條 branch」「branch 要收尾了」「準備送 PR」「整理這條分支」「wrap up branch」「這條 branch 做完了」時使用。
allowed-tools: Bash(git:*) Bash(python3:*) Bash(grep:*) Read Edit
metadata:
  keywords: "wrap-up, 收尾, PR, 準備送PR, branch收尾, 整理分支, feature完成, ship, finalize"
  argument-hint: "[skip-annotate] [skip-review] [skip-pr-draft] [no-push]"
  user-invocable: "true"
---

# Branch Wrap-Up — Feature Branch 收尾一站式流程

> 整合 `branch-diff-annotator`、`branch-diff-code-review`、`smart-commit-flow` 三個 Skill，在 feature branch 完成後依序執行並以 review gate 把關 commit 品質。
> 直接觸發：`/branch-wrap-up $ARGUMENTS`

---

## Trigger cues（啟用條件）

- 「幫我收尾這條 branch」
- 「branch 要收尾了，整理一下」
- 「準備送 PR」
- 「整理這條分支」
- 「wrap up branch」
- 「這條 branch 做完了，來收尾」
- 直接輸入 `/branch-wrap-up`

## Non-trigger cues（不該啟用）

- 只是問 git 操作、沒有完成 feature 要收尾
- 只想單獨做 code review（改用 `/branch-diff-code-review`）
- 只想補 docstring（改用 `/branch-diff-annotator`）
- 只想 commit（改用 `/smart-commit-flow`）
- 只想要 PR 標題與描述草稿（改用 `/branch-diff-pr-description`）
- 沒有在 git repo 內

---

## Arguments（$ARGUMENTS 解析）

自由文字，以下為常見旗標（組合使用也可）：

| 旗標 | 效果 |
|---|---|
| `skip-annotate` | 跳過 Step 2（補 docstring） |
| `skip-review` | 跳過 Step 4（code review）與 Step 5（review gate） |
| `skip-pr-draft` | commit 後不詢問是否產出 PR 草稿 |
| `no-push` | commit 後不詢問 push |

---

## Operating procedure（流程）

### Step 0 — 環境前置檢查與分支確認（必做）

執行以下檢查，任一失敗則說明原因並終止：

```bash
# 確認在 git repo 內
git rev-parse --is-inside-work-tree

# 確認當前分支不是 main / master（避免誤操作主線）
CURRENT_BRANCH=$(git branch --show-current)
# 若 CURRENT_BRANCH 為 main 或 master，終止並警告

# 找出 branch base（後續步驟共用）
BASE=$(git merge-base HEAD main 2>/dev/null || git merge-base HEAD master 2>/dev/null || git merge-base HEAD develop 2>/dev/null)
BASE_REF=$(git for-each-ref --format='%(refname:short)' refs/heads/main refs/heads/master refs/heads/develop 2>/dev/null | head -1)
BASE_SHORT=$(git rev-parse --short $BASE 2>/dev/null)
# 若 BASE 為空，終止並說明無法找到 base branch

# 確認有 branch diff（相對於 base 有改動）
CHANGED_FILES=$(git diff --name-only $BASE..HEAD | wc -l | tr -d ' ')
# 若 CHANGED_FILES 為 0，終止並提示沒有需要收尾的改動

# 確認 python3 可用（供 review bundle 與 commit bundle 使用）
python3 --version
```

檢查通過後，輸出確認畫面並**暫停等待使用者確認**：

```
## Branch Wrap-Up — 確認收尾目標

  當前分支：<branch-name>
  合併基準：<base-ref> (<base-short-sha>)
  異動檔案：<N> 個
  HEAD commit：<head-short-sha> <head-commit-subject>

即將依序執行：TODO 掃描 → 補 docstring → code review → commit → PR 草稿

確認以上分支資訊正確，開始收尾流程？(y/n)
```

- 若使用者輸入 `n`：終止流程，提示可切換到正確分支後重新執行 `/branch-wrap-up`
- 若使用者輸入 `y`：繼續，並在確認後輸出大型 diff 警告（若適用）：

```
⚠️  偵測到大型 diff（N 個檔案）。整個流程可能需要較長時間，review 輸出將引導你查看對應的 bundle 檔案而非在對話中完整重印。
```

---

### Step 1 — TODO/FIXME 掃描（預設開啟，可帶 `skip-annotate` 旗標跳過本節及 Step 2）

**目標**：只掃 branch diff 中**新增的** TODO/FIXME markers，不報告既有的。

```bash
git diff $BASE..HEAD | grep -n "^\+.*\(TODO\|FIXME\|HACK\|XXX\|TEMP\)" | grep -v "^+++ "
```

輸出格式（若有發現）：

```
## TODO/FIXME 掃描結果

以下 markers 是本次 branch 新增的，請確認是否在 commit 前清除：

- `path/to/File.kt:42` — TODO: 這裡要補充錯誤處理
- `path/to/Service.kt:87` — FIXME: 暫時跳過驗證，上線前要補

是否繼續流程？(y/n)
（若選 n，流程終止；修改後重新執行 /branch-wrap-up）
```

若無發現，顯示一行 `✓ 沒有發現新增的 TODO/FIXME` 並繼續。

---

### Step 2 — 補 docstring（branch-diff-annotator 工作流程）

> 完整規範以 `branch-diff-annotator/SKILL.md` 為準。以下為本 skill 執行時的精確步驟。

若 `$ARGUMENTS` 包含 `skip-annotate`，顯示 `[跳過] 補 docstring` 並直接進入 Step 3。

**2-1. 取得 Diff 範圍**

使用 Step 0 已計算的 `$BASE`：
```bash
git diff $BASE..HEAD
```

整理出：哪些檔案被修改（排除已刪除）、每個檔案中哪些行（`+` 開頭）是新增內容。

**2-2. 找出需要補 docstring 的目標**

對每個有改動的檔案：
1. 讀取完整檔案內容（用 Read 工具）
2. 對照 diff 新增行，定位新增或修改的**函式、方法、類別、屬性宣告**
3. 檢查這些宣告上方是否已有完整的 docstring
4. 只處理 diff 中有 `+` 的宣告；已有完整 docstring 的跳過

**2-3. 偵測規範優先順序**

依序讀取：
1. `CLAUDE.md`、`.claude/`、`docs/` 中有關 docstring 格式的說明（專案規範）
2. 依偵測到的語言套用標準（Kotlin → KDoc、Python → PEP 257、JS/TS → JSDoc、Java → Javadoc）
3. 同一檔案中已有的 docstring 格式（保持一致）

**2-4. 撰寫並寫入 Docstring**

用 Edit 工具直接修改原始檔案。內容包含：用途說明、Parameters、Return value、Throws。
行內說明只在 WHY 不明顯時加（不解釋 WHAT）。

**2-5. 輸出摘要並進行 Staging 橋接（Step 3）**

```
## Docstring 加入報告

**`path/to/File.kt`**
- `fun fetchUser(id: String)` — 加入 KDoc（@param id、@return User?）

共修改 N 個檔案，加入 M 個 docstring。
```

---

### Step 3 — Docstring 修改的 Staging 橋接

> 只在 Step 2 有實際修改檔案時執行。若跳過 Step 2 或無修改，直接進入 Step 4。

列出被 branch-diff-annotator 修改的檔案：
```bash
git diff --name-only
```

詢問：

```
以上 N 個檔案已加入 docstring 但尚未 staged。
是否將這些修改納入本次 commit？(y/n)
（若選 n，這些 docstring 修改將保留在工作目錄，之後可以手動 git add）
```

若選 `y`：
```bash
git add <列出的修改檔案路徑>
```

⚠️ **不可逆提醒**：若希望取消 docstring 修改，可執行 `git checkout -- <files>` 還原。

---

### Step 4 — Code Review（branch-diff-code-review 工作流程）

> 完整規範以 `branch-diff-code-review/SKILL.md` 為準。以下為本 skill 執行時的精確步驟。

若 `$ARGUMENTS` 包含 `skip-review`，顯示 `[跳過] Code Review（也跳過 Review Gate）` 並直接進入 Step 6。

**4-1. 找出分支起點**

```bash
SHARED_SCRIPTS="$HOME/.claude/skills/shared/scripts"
python3 "$SHARED_SCRIPTS/branch_base.py"
```

若腳本不存在，回退至 Step 0 計算的 `$BASE`。

**4-2. 產生 Review Bundle**

```bash
python3 "$REVIEW_SKILL_DIR/scripts/build_review_bundle.py"
```

產出 `.ai-artifacts/branch-diff-code-review/` 資料夾，包含 `manifest.json` 及 chunks（或 `all-in-one.md`）。

**4-3. 逐 chunk Review**

依序讀取 `.ai-artifacts/branch-diff-code-review/chunks/*.md`（或 `all-in-one.md`），對每個 chunk 輸出：
- 重大問題（P0/P1/P2 分級）
- 商業邏輯/產品行為建議
- 逐檔案建議（含 diff 行號）

**4-4. 彙總總報告 + 100 分評分**

讀取 `$REVIEW_SKILL_DIR/references/scoring-rubric.md` 進行評分（6 項加總 100 分）。

最終輸出必須包含：Review 範圍、Executive summary、P0/P1/P2 清單、逐檔案建議、商業邏輯建議、測試建議、評分表（含扣分依據）、假設與限制。

---

### Step 5 — Review Gate（P0 硬性阻擋）

> 只在 Step 4 執行後觸發。

根據 Step 4 的評分結果：

**情況 A — 有 P0 問題**：
```
🚫 Review Gate：偵測到 P0 問題，無法繼續 commit。

必須修正以下問題後，重新執行 /branch-wrap-up：
- [P0] <問題描述>（<檔案:行號>）
- [P0] <問題描述>（<檔案:行號>）

流程終止。
```

**情況 B — 無 P0，但總分 < 70**：
```
⚠️  Review Gate：總分 <N>/100，品質未達建議標準。

主要問題：
- <P1 問題摘要>

確認繼續 commit？(y/n)
```
使用者必須明確輸入 `y` 才繼續；輸入 `n` 終止流程。

**情況 C — 無 P0 且總分 ≥ 70**：
```
✓ Review Gate 通過（<N>/100）。繼續 commit 流程。
```

---

### Step 6 — Commit（smart-commit-flow 工作流程）

> 完整規範以 `smart-commit-flow/SKILL.md` 為準。以下為本 skill 執行時的精確步驟。

**6-0. 建立 Git Context Bundle**

```bash
COMMIT_SKILL_DIR="$HOME/.claude/skills/smart-commit-flow"
python3 "$COMMIT_SKILL_DIR/scripts/build_commit_bundle.py"
```

讀取 `.ai-artifacts/smart-commit-flow/commit_bundle.md` 及 `.ai-artifacts/smart-commit-flow/commit_bundle.json`。

**6-1. 確認 staged 範圍**

若 staged 為空但有 unstaged，詢問是否 stage（用 `(y/n)` 格式）。

**6-2. 產生 3 個候選 commit message**

讀取 `$COMMIT_SKILL_DIR/references/commit-message-standard.md` 並產生：
- [1] 候選 A：最精準、最保守
- [2] 候選 B：偏使用者/產品語意
- [3] 候選 C：偏工程語意
- [R] 重新產生
- [I] 自填（含格式檢查）
- [A] 放棄

預設使用繁體中文（除非 `$ARGUMENTS` 含 `en`）。

**6-3. 選擇後直接 commit（不需再確認）**

**6-4. Push 前確認**

- 若 `$ARGUMENTS` 含 `no-push`：跳過，列出手動 push 指令
- 其他：列出 remote、檔案變更摘要、commit message，詢問 `是否 push？(y/n)`

---

### Step 7 — PR Description 草稿（選做，branch-diff-pr-description 工作流程）

> 完整規範以 `branch-diff-pr-description/SKILL.md` 為準。以下為本 skill 執行時的精確步驟。

Commit 成功後詢問是否產出。若 `$ARGUMENTS` 含 `skip-pr-draft`，跳過本步驟。

```
是否產出 PR description 草稿？(y/n)
```

若選 `y`：

**7-1. 決定模板（專案模板優先）**

用 **Glob 工具**依下列**優先序**偵測（取第一個命中的位置，不是把全部命中拿去問），命中即以它為骨架（章節結構不增刪、不調換順序）：

```
1. .github/PULL_REQUEST_TEMPLATE.md（含 pull_request_template.md 大小寫變體）
2. .github/PULL_REQUEST_TEMPLATE/*.md
3. .gitea/PULL_REQUEST_TEMPLATE.md
4. .gitlab/merge_request_templates/*.md
5. PULL_REQUEST_TEMPLATE.md
6. docs/PULL_REQUEST_TEMPLATE.md
```

⚠️ macOS/Windows 檔案系統不分大小寫，大小寫變體會命中同一檔案 —— 判斷數量前先依實際路徑去重。
只有「多模板目錄去重後仍 > 1 份」才列出讓使用者選；全無命中 → 讀 `$HOME/.claude/skills/branch-diff-pr-description/references/pr-description-template.md`。

**7-2. 填充內容**

基於以下資訊填充（HTML 註解填完移除；checkbox 一律留空給使用者確認）：
- `git log $BASE..HEAD --pretty=format:'%h %s'`（依 Conventional Commits type 分組 Changes）
- `git diff $BASE..HEAD --stat`（改動統計）
- Step 4 的 Executive summary 與未修的 P1/P2（若有執行 review）
- 當前 branch 名稱（推斷 ticket ID 與功能範圍）

推不出來的欄位留空並標註 `<!-- 待補 -->`，不要捏造。

**7-3. 輸出標題與草稿**

先給一行建議標題（單一 commit 沿用其 header；多 commit 彙整成一句 Conventional Commits subject），再輸出草稿。

**輸出格式要求（方便複製貼上）**：

用一個 markdown code block 包住整份草稿，並在前後加上分隔提示，讓使用者可以直接框選複製：

````
以下為 PR description 草稿，請複製後貼到 GitHub/GitLab/Gitea：

```markdown
## Summary

- xxx

## Changes

**Features / Fixes**
- xxx

## Testing

- [ ] xxx
```
````

整份草稿以純 Markdown 語法撰寫（heading、bullet、checkbox），不加任何解說文字在 code block 內部。code block 外可以有簡短說明（例如「已根據 review 結果調整 Summary」）。

---

## Output contract（收尾摘要格式）

整個流程完成後，輸出一份「收尾摘要」：

```
## Branch Wrap-Up 完成摘要

| 步驟 | 狀態 | 備註 |
|---|---|---|
| 環境檢查 | ✓ | Branch: feature/xxx → Base: main (abc1234) |
| TODO/FIXME 掃描 | ✓ | 無新增 markers |
| 補 docstring | ✓ | 修改 3 個檔案，加入 7 個 docstring |
| Code Review | ✓ | 85/100，P0: 0，P1: 2，P2: 3 |
| Review Gate | ✓通過 | 85 ≥ 70 且無 P0 |
| Commit | ✓ | feat(auth): 新增 OAuth 登入流程 (sha: abc1234) |
| PR 草稿 | [跳過] | — |
```

---

## Error handling

| 情境 | 處理方式 |
|---|---|
| python3 不可用 | 提醒安裝 python3；branch-diff-code-review 改以人工逐檔 review |
| `branch_base.py` 或 `build_review_bundle.py` 不存在 | 提示可能是 Skill 未正確安裝；改以 `git diff $BASE..HEAD` 直接 review |
| `build_commit_bundle.py` 不存在 | 改以 `git diff --staged` 直接產生 commit message |
| 中途終止後工作樹有 docstring 修改 | 提醒使用者：`git diff --name-only` 查看修改檔案；`git checkout -- <files>` 還原 |
| Branch 為 main/master | 終止並警告：請先建立 feature branch |
| `branch-diff-pr-description` 未安裝（內建模板讀不到） | 專案有 PR 模板則直接沿用；否則以最小骨架產出（`## Summary` / `## Changes` / `## Testing`），並告知草稿結構為簡化版 |

---

## Progressive disclosure map

- Step 2 的完整 docstring 格式規範 → `branch-diff-annotator/SKILL.md`
- Step 4 的 chunking 策略 → `branch-diff-code-review/references/chunking.md`
- Step 4 的 review 檢查清單 → `branch-diff-code-review/references/review-checklist.md`
- Step 4 的評分規則 → `branch-diff-code-review/references/scoring-rubric.md`
- Step 6 的 commit message 規範 → `smart-commit-flow/references/commit-message-standard.md`
- Step 7 的完整 PR 草稿規範 → `branch-diff-pr-description/SKILL.md`
- Step 7 的內建模板 → `branch-diff-pr-description/references/pr-description-template.md`
