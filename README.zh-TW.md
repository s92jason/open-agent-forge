# open-agent-forge

[English](README.md) | **繁體中文**

給 AI coding agent 用的 skill 與 plugin：支援 [Claude Code](https://code.claude.com/docs)、
Codex CLI、GitHub Copilot CLI，以及其他讀得懂
[Agent Skills](https://agentskills.io/specification) 格式的工具。

這裡的每一樣東西在公開之前都**驗證過，也去識別化過**。發佈前會自動掃描，只要發現真實的
公司識別碼、內部代號或憑證，就會擋下來不發佈。

> **語言。** Skill 以繁體中文撰寫，預設也用繁體中文回覆。多數 skill 的說明同時帶有英文關鍵字。

## 目錄結構

```
open-agent-forge/
├── .claude-plugin/
│   └── marketplace.json        # plugin 目錄，Claude Code、Codex CLI、Copilot CLI 都讀這個檔
├── plugins/                    # 完整的 plugin
│   └── <plugin>/
│       ├── .claude-plugin/plugin.json
│       ├── skills/<skill>/     # SKILL.md、references/、scripts/
│       └── shared/             # 只有 forge-git-flow 有：它的 skill 共用的輔助腳本
└── skills/                     # 同一批 skill，一個 skill 一個資料夾，不分 plugin
    ├── <skill>/
    └── shared/                 # forge-git-flow 的 shared/ 的副本
```

每個 skill 都放了兩份：一份在它的 plugin 裡（`plugins/<plugin>/skills/<skill>/`），一份獨立放
（`skills/<skill>/`）。兩份來自同一次發佈，內容一定相同。你用的工具有 plugin 機制就用
`plugins/`；沒有，或只想拿一個資料夾，就用 `skills/`。

## 安裝

### 用 plugin 安裝（建議）

先把這個 repo 加成 plugin marketplace，再安裝你要的 plugin。下面的範例裝的是
`forge-git-flow`，可以換成 [Plugins](#plugins) 表格裡的任何一個名稱。

**Claude Code**

```bash
claude plugin marketplace add s92jason/open-agent-forge
claude plugin install forge-git-flow@open-agent-forge
```

在對話裡輸入 `/plugin marketplace add s92jason/open-agent-forge` 與
`/plugin install forge-git-flow@open-agent-forge` 也是一樣的效果。

**Codex CLI**

```bash
codex plugin marketplace add s92jason/open-agent-forge
codex plugin add forge-git-flow@open-agent-forge
```

**GitHub Copilot CLI**

```bash
copilot plugin marketplace add s92jason/open-agent-forge
copilot plugin install forge-git-flow@open-agent-forge
```

### 只裝單一個 skill

用 [`skills` CLI](https://github.com/vercel-labs/skills)：

```bash
npx skills add s92jason/open-agent-forge --skill feature-spec-builder
```

或是把資料夾複製到你的工具的 skill 目錄：

```bash
git clone https://github.com/s92jason/open-agent-forge.git
cp -r open-agent-forge/skills/feature-spec-builder ~/.claude/skills/
```

| 工具 | 個人的 skill 目錄 |
|------|-------------------|
| Claude Code | `~/.claude/skills/` |
| Codex CLI | `~/.agents/skills/` |
| GitHub Copilot CLI | `~/.copilot/skills/` 或 `~/.agents/skills/` |

有幾個 skill 需要旁邊有其他資料夾，[Skills](#skills) 表格裡有標出來。不確定的話就裝
plugin：skill 需要的東西它一定都會帶上。

### 使用 skill

直接用自然語言描述你要做的事，或是用名稱呼叫。在 Claude Code 裡，透過 plugin 安裝的 skill
是 `/forge-git-flow:pr-review`；同一個 skill 以單一資料夾複製進去則是 `/pr-review`。

## Plugins

| Plugin | 涵蓋的範圍 | 內容 |
|--------|------------|------|
| **forge-git-flow** | Git 工作流：從建立 branch，到 review、commit 與撰寫 PR 描述 | 8 個 skill |
| **forge-spec** | 從設計稿或現有的程式碼整理出工程規格文件 | 1 個 skill |
| **forge-hiring** | 面試作業評分 | 1 個 skill |
| **forge-toolkit** | 任何技術棧、任何任務都適用的工作方法 | 1 個 skill |

## Skills

| Skill | Plugin | 做什麼 | 能不能單獨使用 |
|-------|--------|--------|----------------|
| **branch-diff-code-review** | forge-git-flow | 審查分支起點到 `HEAD` 之間的 diff，大的 diff 會自動分成幾個 chunk，並以 100 分評分。 | 需要 `shared/` |
| **pr-review** | forge-git-flow | 給 PR 編號或網址就能 review Gitea 的 pull request，不會動到你正在工作的分支。它會把變更分組、寫出導讀，並在本機頁面上把 AI 的意見放在 diff 的那一行旁邊；你可以採用或忽略這些意見、寫自己的留言，最後一次送出成一份 review。作者補 commit 之後可以接著做下一輪。 | 需要 `shared/` 與 `branch-diff-code-review/` |
| **branch-wrap-up** | forge-git-flow | Feature branch 收尾一次做完：TODO 掃描、補 docstring、code review、commit、PR 草稿。 | 會呼叫另外四個 git-flow skill |
| **branch-diff-unit-test** | forge-git-flow | 為分支上改到的業務邏輯類別補 unit test（Android：JUnit、MockK、coroutines），目標 branch coverage 90% 以上。 | 可以 |
| **branch-diff-annotator** | forge-git-flow | 為分支上改到的程式碼補 docstring（KDoc、JSDoc、PEP 257）。 | 可以 |
| **branch-diff-pr-description** | forge-git-flow | 依分支的 diff 產生 PR 標題與描述草稿，專案有自己的 PR 模板就優先採用。全程唯讀。 | 可以 |
| **smart-commit-flow** | forge-git-flow | 提出幾個 commit message 讓你選，commit 之後要你確認才會 push。 | 可以 |
| **create-git-branches** | forge-git-flow | 從同一個確認過的 commit 建立多條相關的 branch，命名規則從你既有的 branch 推導出來。 | 可以 |
| **feature-spec-builder** | forge-spec | 把 Axure、Figma 與 API 來源整理成一份 `FEATURE-SPEC.md`，給開發、QA 與 AI agent 共用。有 Create、Update、Code Sync 三種模式。[README](skills/feature-spec-builder/README.md) | 可以 |
| **android-hw-grader** | forge-hiring | 評 Android 面試作業：管理題目與評分標準、分析專案，輸出結構化的評語與分數。 | 可以 |
| **task-brief** | forge-toolkit | 把一句需求轉成新的 Claude Code session 的交接包：建議的 model、effort 與 permission mode、kickoff prompt，以及啟動指令。全程唯讀。 | 可以 |

「需要 `shared/`」的意思是：把 `skills/shared/` 一起複製到和這個 skill 同一個 skill 目錄裡。
`branch-wrap-up` 會呼叫 `branch-diff-annotator`、`branch-diff-code-review`、
`smart-commit-flow` 與 `branch-diff-pr-description`，所以這幾個要一起裝。

## 需求

- 一個支援的 agent：Claude Code、Codex CLI、GitHub Copilot CLI，或其他讀得懂 Agent Skills
  的工具
- **Python 3.9 以上**。腳本只用標準函式庫
- **git**：forge-git-flow 的 skill 會用到
- 一個 **Gitea** 站台：`pr-review` 會用到

各個 skill 自己的前置條件與憑證設定，請看它的 `SKILL.md`。

## 相容性

這些 skill 平常是在 Claude Code 裡開發與使用的。為了讓它們在其他工具也能用：

- `SKILL.md` 的 frontmatter 只用每個支援的工具都接受的最上層欄位，工具專屬的欄位放在
  `metadata` 底下。
- Plugin 的安裝在 Claude Code、Codex CLI 與 GitHub Copilot CLI 上檢查過。

有些 skill 會用到 Claude Code 的功能（例如 subagent、slash command 的參數），在其他工具裡的
行為可能不一樣。

## 這個 repo 怎麼維護

`plugins/` 與 `skills/` 的內容是由同步腳本從另一個工作用的 repo 發佈過來的，同一支腳本也會
更新 `.claude-plugin/marketplace.json`。直接改這兩個資料夾的內容，下次發佈時會被蓋掉，所以
請不要在 pull request 裡修改它們。歡迎開 issue，或在 pull request 裡描述你想要的改動，
會由來源那一邊套用。

## 貢獻

請看[貢獻指南](CONTRIBUTING.zh-TW.md)。最重要的一條：絕對不要提交真實的憑證或識別碼。
這是一個公開、去識別化的工具集。

## 授權

MIT，詳見 [LICENSE](LICENSE)。
