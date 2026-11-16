---
name: branch-diff-pr-description
description: |
  依當前 git branch 的 diff（branch base..HEAD）產生可直接貼上的 PR 標題與描述草稿。
  優先採用專案自帶的 PR 模板（.github / .gitea / .gitlab），沒有才用內建模板；
  內容參考 commit 歷史、diff 統計與既有 code review 報告填充。
  全程唯讀，不修改任何檔案、不建立 PR。
  當使用者說「幫我寫 PR 描述」「產生 PR 標題」「PR description」「幫我生 PR 內容」
  「這條 branch 的 PR 要怎麼寫」時使用。
allowed-tools: Bash(git:*) Bash(python3:*) Read Glob
metadata:
  keywords: "PR, pull request, PR描述, PR標題, description, 送PR, merge request, MR, branch, diff"
  argument-hint: "[en] [title-only]"
  user-invocable: "true"
---

# Branch Diff PR Description — 產生 PR 標題與描述草稿

> 依 branch base..HEAD 的 diff 與 commit 歷史，產出一份可直接貼到 GitHub / GitLab / Gitea 的 PR 標題與描述。
> **全程唯讀**：不修改任何檔案、不 push、不建立 PR。
> 直接觸發：`/branch-diff-pr-description $ARGUMENTS`

---

## Trigger cues（啟用條件）

- 「幫我寫 PR 描述」「幫我生 PR 內容」
- 「產生 PR 標題」「PR title 要怎麼下」
- 「這條 branch 的 PR 要怎麼寫」
- 「幫我準備 PR description」
- 直接輸入 `/branch-diff-pr-description`

## Non-trigger cues（不該啟用）

- 要跑完整的 branch 收尾流程（改用 `/branch-wrap-up`）
- 只想做 code review（改用 `/branch-diff-code-review`）
- 只想 commit（改用 `/smart-commit-flow`）
- 要求「幫我開 PR / 建立 PR」——本 skill 只產草稿，需說明並提供 `gh pr create` / `tea pr create` 指令讓使用者自行執行
- 沒有在 git repo 內

---

## Arguments（$ARGUMENTS 解析）

自由文字，以下為常見旗標（可組合）：

| 旗標 | 效果 |
|---|---|
| `en` | 描述內容改用英文（預設繁體中文） |
| `title-only` | 只產生 PR 標題，跳過 Step 2/3/5 的描述產生 |

---

## Operating procedure（流程）

### 成功標準（你要以此自我檢查）

- **不捏造**：每一條 Summary / Changes 都能對應到實際的 commit 或 diff
- **模板忠實**：若專案有自帶 PR 模板，輸出結構必須與該模板一致（章節不增刪、順序不調換）
- **可直接複製**：標題單獨一行、描述用單一 markdown code block 包住
- **唯讀**：全程沒有任何寫檔、commit、push、建立 PR 的動作

---

### Step 0 — 環境檢查與 branch base 解析（必做）

優先使用共用腳本解析 branch base，與其他 branch-diff 系列 skill 共用同一套邏輯（自動支援 `BASE_COMMIT` / `BASE_REF` 環境變數覆寫、遠端 ref 防呆）：

```bash
# 確認在 git repo 內
git rev-parse --is-inside-work-tree

# 確認當前分支不是 main / master
CURRENT_BRANCH=$(git branch --show-current)

SHARED_SCRIPTS="$HOME/.claude/skills/shared/scripts"
BASE_INFO=$(python3 "$SHARED_SCRIPTS/branch_base.py" 2>/dev/null)
BASE=$(echo "$BASE_INFO" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('base_commit') or '')" 2>/dev/null)
BASE_REF=$(echo "$BASE_INFO" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('base_ref') or '')" 2>/dev/null)

# Fallback：共用腳本不存在或解析失敗
if [ -z "$BASE" ]; then
  BASE=$(git merge-base HEAD main 2>/dev/null \
       || git merge-base HEAD master 2>/dev/null \
       || git merge-base HEAD develop 2>/dev/null)
fi
```

終止條件：

| 情境 | 處理 |
|---|---|
| 不在 git repo 內 | 終止並說明 |
| 當前分支為 `main` / `master` | 終止並提示：主線分支沒有 PR 可寫，請先切換到 feature branch |
| `$BASE` 為空 | 最後 fallback 為 `git diff HEAD`，並在輸出中明確告知「無法判定 branch base，草稿僅涵蓋未提交的改動」 |
| `$BASE..HEAD` 無任何改動 | 終止並提示這條 branch 相對於 base 沒有變更 |

---

### Step 1 — 蒐集素材（唯讀）

執行以下指令並整理成後續填充的依據：

```bash
# commit 清單（推導 Changes 分組）
git log "$BASE..HEAD" --pretty=format:'%h %s'

# 影響範圍與規模
git diff "$BASE..HEAD" --stat

# 檔案增刪改名（判斷是否有破壞性變更）
git diff "$BASE..HEAD" --name-status

# 未提交改動（草稿不涵蓋這些）
git status --porcelain
```

整理原則：

- **Changes 分組**：依 commit 的 Conventional Commits type 歸類 —— `feat`/`fix` → Features / Fixes，`refactor`/`chore`/`style` → Refactors / Cleanup，`test` → Tests，`docs` → Docs。無 type 前綴的 commit 依 diff 內容判斷
- **Ticket ID**：從 branch 名稱推斷（如 `feature/ABC-123-oauth-login` → `ABC-123`）。推不出來就不要編
- **破壞性變更**：刪除的公開 API、改名的檔案、變更的函式簽章要點出來
- **未提交改動**：若 `git status --porcelain` 非空，在輸出草稿前先提醒：

```
⚠️  偵測到 N 個未提交的改動，本草稿不涵蓋這些內容。
```

若 `$ARGUMENTS` 含 `title-only`，蒐集完素材後直接跳到 Step 4。

---

### Step 2 — 模板解析（專案模板優先，內建為 fallback）

依「專案規範 > 內建預設」的優先序，用 **Glob 工具**（不要用 shell glob，zsh 在未命中時會直接報錯）依序偵測專案自帶的 PR 模板。**清單是優先序，不是候選集** —— 取第一個命中的位置即可，不要把跨位置的命中全部拿去問使用者：

| 順位 | 位置 |
|---|---|
| 1 | `.github/PULL_REQUEST_TEMPLATE.md`（含 `pull_request_template.md` 大小寫變體） |
| 2 | `.github/PULL_REQUEST_TEMPLATE/*.md`（多模板目錄） |
| 3 | `.gitea/PULL_REQUEST_TEMPLATE.md` |
| 4 | `.gitlab/merge_request_templates/*.md` |
| 5 | `PULL_REQUEST_TEMPLATE.md`（repo 根目錄） |
| 6 | `docs/PULL_REQUEST_TEMPLATE.md` |

**⚠️ 大小寫去重（必做）**：macOS（APFS）與 Windows 的檔案系統預設不分大小寫，`PULL_REQUEST_TEMPLATE.md` 與 `pull_request_template.md` 會命中**同一個檔案**。決定「單一 vs 多個」之前，先依實際路徑去重（比對 `git ls-files` 的結果或 realpath），否則會拿兩個相同的檔案去問使用者。

決策：

| 結果 | 處理 |
|---|---|
| 第一個命中的位置只有 1 份模板 | 直接以它為骨架，並在最終輸出告知採用了哪一份 |
| 第一個命中的位置是多模板目錄且去重後 > 1 份 | 列出該目錄內的候選讓使用者選（`(1/2/3)`）。這是唯一無法自動推斷的分歧點 —— 平台本來就設計成讓作者依 PR 類型挑選 |
| 全無命中 | 讀取本 skill 的 `references/pr-description-template.md` |

**填寫規則（硬性）**：

- 專案模板的章節結構**不增不刪不調換順序** —— reviewer 依賴這個結構
- HTML 註解（`<!-- 說明文字 -->`）是給填寫者看的指示，填完後移除
- checkbox 清單保留原樣結構，**勾選狀態一律留空**（`- [ ]`）交給使用者確認，不要代為勾選
- 模板中無法從 diff / commit / review 推得的欄位（Jira 連結、截圖、效能數據等）留空並標註 `<!-- 待補 -->`

---

### Step 3 — 補 review 脈絡（若可用）

檢查是否有 `branch-diff-code-review` 留下的報告：

```bash
test -f .ai-artifacts/branch-diff-code-review/review-output.md && echo exists
```

若存在，**先驗證新鮮度**：讀 `.ai-artifacts/branch-diff-code-review/manifest.json`，比對其 range 與目前的 `$BASE..HEAD`。

| 新鮮度 | 處理 |
|---|---|
| range 相符 | 讀取 `review-output.md`，用其 Executive summary 潤飾 Summary；用 P1/P2 未修項填充 Known issues / Review notes |
| range 不符或無 manifest | 忽略，並在輸出時附註「偵測到既有 review 報告但已過期，未納入」 |

沒有報告就跳過，不需要為了這個而去跑 review。

---

### Step 4 — 產生 PR 標題

依序判斷：

1. **單一 commit**：直接沿用該 commit 的 header（已符合 Conventional Commits 就不要改寫）
2. **多個 commit**：彙整成一句 `<type>(<scope>): <subject>`，type 取影響最大的那類（有 `feat` 就用 `feat`，全是修正就用 `fix`）
3. **Ticket ID**：若 Step 1 推得 ticket ID，依專案既有 PR 慣例決定是否加前綴（可用 `git log --oneline` 觀察主線 merge commit 的標題格式）

標題保持在 72 字元內，用繁體中文（`en` 旗標則用英文）。

---

### Step 5 — 輸出

標題單獨一行方便複製，描述用單一 markdown code block 包住：

````
建議標題：

feat(auth): 新增 OAuth 登入流程

以下為 PR description 草稿（採用專案模板 `.github/PULL_REQUEST_TEMPLATE.md`）：

```markdown
## Summary

- 讓使用者可以用 Google 帳號登入，取代原本僅有的帳密登入

## Changes

**Features / Fixes**
- 新增 `OAuthLoginUseCase`，處理授權碼交換與 token 儲存

## Testing

- [ ] 主要 happy path：Google 帳號首次登入
```

草稿完成。你可以直接複製貼上，或用以下指令建立 PR：
  gh pr create --title "<標題>" --body-file -
  tea pr create --title "<標題>"
````

code block **內部**只放純 Markdown，不加任何解說文字。說明（採用哪份模板、未提交改動警告、review 報告過期提示）放在 code block 外。

---

## Output contract（輸出格式保證）

- 描述內容預設**繁體中文**（除非 `$ARGUMENTS` 含 `en`）；章節標題沿用模板原文
- 標題單獨一行、描述包在單一 markdown code block 內，兩者都可直接框選複製
- 採用的模板來源必須明示（專案模板路徑 or「內建模板」）
- **不捏造**：推不出來的欄位留空並標註 `<!-- 待補 -->`
- **唯讀保證**：不寫檔、不 commit、不 push、不建立 PR。要建 PR 時只提供指令讓使用者自行執行

---

## Error handling

| 情境 | 處理方式 |
|---|---|
| `branch_base.py` 不存在 | 改用 `git merge-base HEAD main/master/develop`；再失敗則 `git diff HEAD` 並告知範圍受限 |
| python3 不可用 | 全程改用純 git 指令（Step 0 的 fallback 路徑即可） |
| 專案模板讀取失敗 | 退回內建模板，並告知偵測到但無法讀取的路徑 |
| 當前分支為 main/master | 終止並提示先切換到 feature branch |
| commit 訊息品質過低（如全是 `wip`、`fix typo`） | 改以 diff 內容為主要依據推導描述，並提示使用者 commit 訊息無法提供有效語意 |

---

## Progressive disclosure map（何時讀什麼）

- Step 0 的 base 解析共用邏輯 → `$HOME/.claude/skills/shared/scripts/branch_base.py`
- Step 2 的內建模板 → `references/pr-description-template.md`
- Step 3 的 review 報告 → `.ai-artifacts/branch-diff-code-review/review-output.md`
- 需要完整收尾流程（含 review 與 commit）→ `branch-wrap-up/SKILL.md`
