# Commit Message 規範（主流：Conventional Commits + 50/72 Rule）

本 Skill 預設以 **Conventional Commits** 的結構當作「最主流且可機器處理」的基準規範，並搭配業界長期常用的 **50/72 rule** 來提升可讀性。

---

## 1) 基本格式（Header 必填）
### Header
- `type`：描述改動類型（見下方 type 列表）
- `scope`（選填）：影響範圍（模組/元件/領域），例如 `ui`、`network`、`build`、`payment`
- `subject`：一句話描述「做了什麼」，中文建議用「精準動詞 + 受詞」

---

## 2) Type 建議集合（兼容主流工具鏈）
- `feat`：新增/擴充功能（對使用者有感）
- `fix`：修 bug（行為更正）
- `refactor`：重構（不改外部行為）
- `perf`：效能改善
- `docs`：文件變更
- `test`：測試新增/調整
- `build`：建置系統/依賴相關
- `ci`：CI 設定
- `chore`：雜項維護（不影響產品行為）
- `style`：純格式（不建議濫用；若只是 lint/format 才用）

---

## 3) Breaking change（如果真的破壞相容）
- 方式 A：在 type 後加 `!`：`feat(api)!: ...`
- 方式 B：在 footer 加 `BREAKING CHANGE: ...`

（不要亂用；只有真的改壞相容、需要呼叫方跟著改才標。）

---

## 4) Body / Footer（可選）
### Body
- 用來回答：**為什麼改（Why）**、**怎麼改（How）**、**跟以前差在哪（Impact）**
- 建議每行 72 字內換行

### Footer
- 放 issue/票號、破壞性變更說明、或其他需要機器解析的 metadata
- 不要憑空捏造票號

---

## 5) 50/72 Rule（可讀性）
- 標題（header）建議 50 字內（中文可稍放寬，但仍要追求精煉）
- header 後空一行
- body 每行 72 字內換行

---

## 6) 中文 commit message 實務建議
- `subject` 用「動詞 + 受詞」：例如「新增 XXX」「修正 XXX」「調整 XXX 行為」「移除 XXX」
- 少用「更新」「修正一些問題」這種低資訊密度句子
- scope 用英文短字更利於工具鏈（例如 `ui`、`aep`、`compose`、`gradle`）

---

## 7) 範例
- `feat(login): 新增 Face ID 登入流程`
- `fix(network): 修正 401 時 token refresh 競態`
- `refactor(ui): 重構首頁卡片渲染以降低重複邏輯`
- `build(gradle): 升級 AGP 並調整 version catalog`
