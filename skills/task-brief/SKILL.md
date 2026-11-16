---
name: task-brief
description: 把一句需求轉成給新 Claude Code session 用的交接包：建議 model / effort / permission mode（附理由與觸發訊號）、可直接貼上的 kickoff prompt、一行啟動指令與 deep link。全程唯讀。當使用者說「幫我寫開新 session 的 prompt」「這件事該用哪個模型」「開新 session 要怎麼下」「幫我準備交接 prompt」「effort 要開多少」，或英文說 "task brief", "write a kickoff prompt for a new session", "which model should I use for this" 時使用。
allowed-tools: Read Glob Grep Bash
metadata:
  keywords: "task brief, 交接, 交接包, kickoff prompt, 開新 session, 新 session, 模型選擇, model, effort, permission mode, 啟動指令, deep link"
  argument-hint: "[需求描述] [--cwd <目標目錄>]"
  user-invocable: "true"
  model: "opus"
  effort: "high"
---

# Task Brief — 新 session 交接包

> 輸入一句需求，輸出一份讓新 session 不必回頭問就能開工的交接包。
> **全程唯讀**：不寫檔、不改 git 狀態、不啟動新 session。
> 直接觸發：`/task-brief $ARGUMENTS`

---

## Trigger cues（啟用條件）

- 「幫我寫開新 session 的 prompt」「幫我準備交接 prompt」
- 「這件事該用哪個模型」「effort 要開多少」「要用 plan mode 嗎」
- 「task brief」「kickoff prompt」
- 直接輸入 `/task-brief`

---

## 參考文件

| 檔案 | 用途 | 何時讀 |
|---|---|---|
| `references/model-effort-rubric.md` | 三個判定軸、訊號清單、判定規則 | 步驟 4，**每次都讀** |
| `references/prompt-template.md` | kickoff prompt 五段骨架與每段要回答的問題 | 步驟 5，**每次都讀** |
| `scripts/build_launch_command.py` | 產生 shell-escaped 啟動指令與 URL-encoded deep link | 步驟 6 |

本 skill 目錄為 `${CLAUDE_SKILL_DIR}`。若該變數未被替換（例如匯出到其他平台），改用與本 SKILL.md 同目錄的相對路徑。

---

## Operating procedure（流程）

### 步驟 1：取得需求

- `$ARGUMENTS` 含 `--cwd <路徑>` → 把路徑取出來當**目標目錄**（展開 `~`、轉成絕對路徑），其餘文字當需求原文。目標目錄可以還不存在（從零建立的新專案）
- `$ARGUMENTS` 有內容 → 當作需求原文，進步驟 2
- `$ARGUMENTS` 是空的 → **只問一題**，問完就等：

  > 要交接給新 session 的需求是什麼？用一句話描述就好。

  不追問細節；需求不清楚的地方之後放進 prompt 的「待確認」。

### 步驟 2：輕量掃描 repo

目的是讓 prompt 帶上專案脈絡，並蒐集 rubric 的訊號。**以 10 次左右的讀取為上限**，不要做完整 code review。

掃描對象：

| 情況 | 掃描哪裡 | 之後的 cwd |
|---|---|---|
| 沒有指定目標目錄 | 目前 repo | 目前 repo 根目錄 |
| 目標目錄已存在 | 目標目錄（Read / Glob / Grep 一律用絕對路徑） | 目標目錄所在 repo 的根目錄 |
| 目標目錄還不存在 | 不掃描程式碼；記為 S4、R2（還不是 git repo），需求以外的脈絡寫「未知」 | 目標目錄 |

1. **定位與 git 狀態**（一次 Bash；`<DIR>` 是目標目錄，沒有指定時省略 `-C "<DIR>"`）：

   ```bash
   git -C "<DIR>" rev-parse --show-toplevel 2>/dev/null || pwd
   git -C "<DIR>" status --porcelain 2>/dev/null | head -20; echo "exit=$?"
   ```

   取得 repo 根目錄的絕對路徑（之後的 cwd）、是否為 git repo、工作區是否乾淨（R1 / R2）。

2. **專案說明**：Read `CLAUDE.md`、`README.md`（只讀開頭到能說出專案是什麼、技術棧、測試指令為止）。
3. **套件或建置檔**：Glob 根目錄的 `package.json`、`build.gradle*`、`settings.gradle*`、`pyproject.toml`、`requirements*.txt`、`go.mod`、`Cargo.toml`、`pom.xml`、`Makefile`、`*.xcodeproj`，讀到的只取語言、框架、模組列表、test script。
4. **測試指令**：依序從 CLAUDE.md 的測試章節、建置檔的 test script、測試目錄（`tests/`、`test/`、`src/test/`、`*_test.*`、`test_*.py`）判斷 R4。
5. **需求點名的對象**：把需求裡的類別名、檔名、模組名拿去 Grep / Glob，記下命中檔數與所在目錄（S0–S4、J2）。**找不到就記下「未找到」**（S0），不要猜位置；只在文件範例裡出現不算找到。命中多個同名檔時，套用 rubric 的「同名檔規則」。
6. **技術棧比對**：需求點名的語言、平台或框架，在第 3 項的建置檔與 git 追蹤的檔案中找不找得到（S5）。

### 步驟 3：偵測規格檔（軟依賴）

用 Bash 列出候選（`git ls-files` 才會略過 `.gitignore` 的內容；macOS 檔案系統不分大小寫，Glob 的 `*-SPEC.md` 會誤撈 `line-spec.md` 之類檔案，所以改用區分大小寫的 grep）：

```bash
git ls-files 2>/dev/null | grep -E '(^|/)(FEATURE-SPEC|SPEC|[A-Z0-9_-]+-SPEC)\.md$|(^|/)(docs|specs?)/.*[Ss]pec[^/]*\.md$' \
  | grep -vE '(^|/)(node_modules|references|agents|skills)/|template' | head -10
```

不是 git repo 時改用 Glob `**/FEATURE-SPEC.md`、`**/SPEC.md`。候選檔還要讀前 30 行確認是規格文件（有需求、規格、驗收之類的章節）；開頭是 `name:` / `description:` frontmatter 的是 agent 或 skill 定義，不算。

- **沒找到** → 略過本步驟，不提 forge-spec，也不要求安裝任何東西
- **找到** → 用標題比對找出與需求相關的段落，列出擬抽的段落標題，問一題：

  > 找到規格檔 `<路徑>`，與需求相關的段落是：<標題 1>、<標題 2>。要把這些段落的重點帶進交接包嗎？（是 / 否）

  - 回答「是」→ 把段落重點濃縮進 prompt 的「背景」，路徑與段落標題寫進「交接資訊」
  - 回答「否」→ 只在「交接資訊」列出規格檔路徑

### 步驟 4：依 rubric 判定

Read `references/model-effort-rubric.md`，照它的規則：

1. 把步驟 1–3 的觀察對到訊號清單，記下編號與實際觀察
2. 三個軸各自**由上往下取第一個成立的**，不折衷
3. 做組合檢查（haiku 的 effort 上限、fable 的 effort 下限、未 commit 改動的降級）

### 步驟 5：撰寫 kickoff prompt

Read `references/prompt-template.md`，照五段骨架寫：背景、目標、驗收條件、限制、交接資訊。

- 需求原文保留在「背景」
- 掃描答不出來的問題放進「交接資訊 → 待確認」
- 不在 prompt 裡寫 model / effort / mode

### 步驟 6：產生啟動指令與 deep link

把 prompt 原文以 quoted heredoc 傳給腳本（quoted heredoc 不展開 `$` 與反引號，prompt 原樣傳入；不寫任何檔案）：

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/build_launch_command.py" \
  --model <model> --effort <effort> --mode <mode> \
  --cwd "<步驟 2 決定的 cwd>" \
  --prompt - <<'TASK_BRIEF_EOF'
<kickoff prompt 原文>
TASK_BRIEF_EOF
```

腳本輸出 JSON：`command`、`deep_link`（不能產生時為 `null`）、`deep_link_omitted_reason`、`prompt_length`、`cwd`、`cwd_exists`。
**不要自己拼指令或 URL**——引號、換行與編碼一律以腳本輸出為準。

### 步驟 7：輸出交接包

固定四段，照下方格式印出。之後不再有其他動作。

---

## 輸出格式

````markdown
# 交接包：<需求一句話摘要>

<（只在 S0 或 S5 且沒有指定目標目錄時）> ⚠️ 目標可能不在 `<掃描的 repo>`：<一句觀察>。建議指定目錄重跑：`/task-brief <需求> --cwd <目標目錄>`

## 1. 建議設定

| 項目 | 建議 | 理由 | 觸發訊號 |
|---|---|---|---|
| model | `<alias>` | <一句理由> | <編號：實際觀察；可多個> |
| effort | `<level>` | <一句理由> | <編號：實際觀察> |
| permission mode | `<mode>` | <一句理由> | <編號：實際觀察> |

## 2. Kickoff prompt

```markdown
<五段 prompt 原文>
```

## 3. 啟動指令

在 `<cwd>` 執行（bash / zsh）：

```bash
<腳本輸出的 command，原樣>
```

## 4. Deep link

<腳本輸出的 deep_link，原樣>

點開後 prompt 會預先填入、但不會自動送出，按 Enter 才開始。
````

- 啟動指令與 deep link 都原樣印出：不截斷、不改寫、不包成 markdown 連結（終端機會把整段 URL 當成可點的連結）
- `deep_link` 為 `null` 時，第 4 段改寫成：「不提供 deep link：<deep_link_omitted_reason>」
- `cwd_exists` 為 `false` 時，第 3 段的「在 `<cwd>` 執行」改寫成：「目錄還不存在。先建立 `mkdir -p '<cwd>'`，再到該目錄執行」。task-brief 本身不建立目錄
- 啟動指令用到 `$'...'` 引號時，補一句：「此指令使用 bash / zsh 的 `$'...'` 引號，fish 等其他 shell 請改用 deep link 或手動貼上 prompt。」

---

## 原則

- **唯讀**：只用 Read / Glob / Grep 與唯讀的 Bash（`git status`、`git rev-parse`、執行本 skill 的腳本）。不寫檔、不建目錄、不 commit、不啟動 `claude`
- **只用可觀察的訊號**：每個建議都要指回 rubric 的訊號編號
- **不編造**：找不到的東西寫「未找到」，不知道的放「待確認」
- **最多問一題**：需求為空時問一次；規格檔存在時問一次。其餘一律不問
