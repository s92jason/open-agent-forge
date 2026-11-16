# 貢獻指南

[English](CONTRIBUTING.md) | **繁體中文**

感謝你願意改善這些工具。

`open-agent-forge` 是一個**公開**的工具集：這裡的每一樣東西在公開之前都驗證過，也去識別化過。
維持它的乾淨，是最重要的一條規則。

## 哪些地方可以在這裡改

這個 repo 大部分的內容，是由同步腳本從另一個工作用的 repo 發佈過來的。所以一項改動要在哪裡
做，取決於它改的是哪裡。

| 路徑 | 在哪裡維護 | 怎麼貢獻 |
|------|------------|----------|
| `plugins/`、`skills/`，以及 `.claude-plugin/marketplace.json` 裡各個 plugin 的那一筆 | 在來源那一邊。每次發佈都會蓋掉 | 開 issue，或在 pull request 裡描述你想要的改動。改動會在來源那一邊套用，隨下一次發佈過來 |
| `README.md`、`README.zh-TW.md`、`CONTRIBUTING.md`、`CONTRIBUTING.zh-TW.md`、`LICENSE` | 這裡 | 開 pull request |
| skill 或 plugin 資料夾裡的 `README.md`、`CHANGELOG.md` | 這裡。發佈時不會動到 | 開 pull request |

直接修改 `plugins/` 或 `skills/` 底下檔案的 pull request 沒辦法照原樣合併，因為下一次發佈會把它
蓋掉。不過在描述裡附上 diff 或一段程式，仍然是說明你的想法最清楚的方式。

## 最重要的一條：絕對不要提交真實的憑證或識別碼

這些工具會處理設計稿、原始碼路徑、pull request 與內部的產出，很容易不小心外流。下面這些絕對
不要提交，也不要貼進 issue 或 pull request：

- Token、存取碼，或帶有存取碼的網址
- 真實的公司套件名稱、repo 名稱、主機名稱或內部代號
- 任何 `references/examples/` 裡真實的 API 合約或業務規則

請改用中性的替代內容（`com.example.app`、一個通用的功能名稱）。

## 語言

- **Skill**（`SKILL.md` 與 `references/`）以繁體中文撰寫。提出的改動請和既有的風格一致。
  歡迎提供參考文件的英文版，但請和繁體中文並列，不要取代它。
- **`scripts/` 裡的註解**沿用那個檔案原本使用的語言。
- **README 與 CHANGELOG** 以英文撰寫，讓各地的人都容易上手。最上層的 README 與這份指南另外有
  繁體中文版；改了其中一份，請把另一份一起更新。

## 提出對 skill 的改動

不論是開 issue，還是在 pull request 裡畫出改動的樣子，改動都要符合這幾條：

1. **腳本不要有外部相依。** 腳本只用 Python 標準函式庫（最低 Python 3.9）。沒有先討論過，
   請不要加第三方套件。
2. **測試你動到的腳本。** 在那個 skill 的 `scripts/` 底下：
   ```bash
   python3 -m py_compile *.py          # 語法
   python3 <script>.py --help          # 指令列的基本檢查
   ```
3. **`SKILL.md` 要維持各工具都能用。** `name` 和資料夾名稱相同、`description` 不超過 1024 個
   字元，工具專屬的欄位放在 `metadata` 底下。

## 提出新的 skill

開一個 issue，說明這個 skill 做什麼、agent 在什麼情況下該用它。這個工具集裡的 skill：

- 放在某個 plugin 裡，和相關的 skill 在一起：

  ```
  plugins/<plugin>/skills/<skill>/
  ├── SKILL.md          # agent 載入的進入點
  ├── references/       # 繁體中文的參考文件
  └── scripts/          # 只用標準函式庫的 Python
  ```

- 可以依賴同一個 plugin 裡的其他 skill，或那個 plugin 的 `shared/` 腳本，但不能依賴別的 plugin
- 要說明從 `skills/` 單獨複製它的資料夾時，旁邊還需要什麼。README 的 Skills 表格會記下這件事
- 已經去識別化，符合上面最重要的那一條

新的 skill 會先加在來源那一邊，再發佈到這裡的 `plugins/` 與 `skills/`。
