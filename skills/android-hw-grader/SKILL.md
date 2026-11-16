---
name: android-hw-grader
description: Android 面試作業評分工具：管理題目與評分標準（新增/選擇/刪除），分析當前目錄的 Android 專案並輸出結構化評語與分數
allowed-tools: Bash(python3:*) Read Grep Glob
metadata:
  argument-hint: "[list | add | update <name> | delete <name> | grade <name>]"
  user-invocable: "true"
---

# Android HW Grader

> 這個 Skill 目標：**管理面試作業題目（新增/列出/刪除），並針對當前目錄的 Android 專案進行自動評分，輸出結構化評語與分數。**
> 你也可以用指令直接觸發：`/android-hw-grader $ARGUMENTS`

## Direct invocation（指令觸發）
- 使用者輸入 `/android-hw-grader ...` 時，**強制啟動**本 Skill。
- `$ARGUMENTS` 決定執行哪個子指令：

| 指令 | 動作 |
|------|------|
| （無參數） | 列出所有題目 → 互動選題號，再選操作（評分/修改/刪除）或新增 |
| `list` | 列出所有已儲存的題目 |
| `add` | 互動收集題目名稱與 prompt → 存檔 |
| `update <name>` | 互動修改指定題目的 prompt |
| `delete <name>` | 刪除指定題目 |
| `grade <name>` | 以指定題目的評分標準，評分當前目錄的 Android 專案 |

---

## Operating procedure（流程）

### SCRIPT_PATH 常數
```
SCRIPT_PATH = plugins/forge-hiring/skills/android-hw-grader/scripts/assignment_manager.py
```
以下流程中所有 `python3 $SCRIPT_PATH` 皆指此路徑。

---

### 指令：list（列出題目）

1. 執行：`python3 $SCRIPT_PATH list`
2. 解析回傳的 JSON 陣列
3. 若為空陣列 → 告知使用者目前沒有題目，詢問是否要新增
4. 否則以表格呈現：

```
| 題目名稱 | 建立時間 |
|----------|----------|
| basic-todo-app | 2026-02-05 |
| mvvm-weather   | 2026-02-04 |
```

---

### 指令：add（新增題目）

1. 詢問使用者題目名稱（允許中文、英數字、底線、連字號，不允許空白與特殊符號）
2. 詢問使用者輸入題目的 prompt（包含題目說明與評分標準）
   - 提示使用者：「請貼上完整的題目說明與評分標準（Markdown 格式）」
3. 將使用者提供的 prompt 透過 heredoc stdin 傳入：
   ```bash
   python3 $SCRIPT_PATH add --name <name> --prompt - <<'PROMPT_EOF'
   <使用者提供的 prompt 內容>
   PROMPT_EOF
   ```
4. 確認回傳 JSON 中 `"status": "created"` → 告知使用者新增成功
5. 若回傳錯誤 → 顯示錯誤訊息

---

### 指令：update \<name>（修改題目）

1. 先執行 `python3 $SCRIPT_PATH get <name>` 確認題目存在
2. 顯示現有 prompt 內容供參考：
   ```
   【現有 prompt 內容】
   <prompt 內容>
   ```
3. 詢問使用者：「請貼上新的題目說明與評分標準（Markdown 格式），將完整取代現有內容：」
4. 以 heredoc stdin 傳入新 prompt：
   ```bash
   python3 $SCRIPT_PATH update --name <name> --prompt - <<'PROMPT_EOF'
   <使用者提供的新 prompt 內容>
   PROMPT_EOF
   ```
5. 確認回傳 JSON 中 `"status": "updated"` → 告知使用者修改成功
6. 若回傳錯誤 → 顯示錯誤訊息

---

### 指令：delete \<name>（刪除題目）

1. 先執行 `python3 $SCRIPT_PATH get <name>` 確認題目存在
2. 詢問使用者確認：「確定要刪除題目 `<name>` 嗎？(y/n)」
3. 使用者確認後執行：`python3 $SCRIPT_PATH delete <name>`
4. 確認回傳 JSON 中 `"status": "deleted"` → 告知使用者刪除成功

---

### 指令：grade \<name>（評分）

這是本 Skill 的核心流程。

#### Step 1 — 載入題目
1. 執行：`python3 $SCRIPT_PATH get <name>`
2. 解析回傳的 JSON，取得 `prompt` 欄位
3. 若找不到題目 → 列出可用題目，詢問使用者要用哪個

#### Step 2 — 確認 Android 專案
1. 使用 Glob 掃描當前目錄，確認存在以下任一檔案：
   - `**/build.gradle`、`**/build.gradle.kts`
   - `**/AndroidManifest.xml`
2. 若找不到 → 告知使用者「當前目錄似乎不是 Android 專案」，終止

#### Step 3 — 讀取原始碼
依序讀取以下檔案（存在才讀）：

**專案設定檔：**
- `build.gradle` / `build.gradle.kts`（根目錄）
- `app/build.gradle` / `app/build.gradle.kts`
- `settings.gradle` / `settings.gradle.kts`
- `gradle/libs.versions.toml`

**主要原始碼：**
- `app/src/main/**/*.kt`（所有 Kotlin 原始碼）
- `app/src/main/**/*.java`（所有 Java 原始碼，若存在）
- `app/src/main/res/layout/**/*.xml`（布局檔案）
- `app/src/main/res/values/**/*.xml`（資源值）
- `app/src/main/AndroidManifest.xml`

**測試碼：**
- `app/src/test/**/*.kt`（單元測試）
- `app/src/androidTest/**/*.kt`（Android 測試）

> **注意**：若檔案數量過多（> 50 個），優先讀取：
> - 所有 `*.kt` / `*.java` 原始碼
> - `build.gradle*` 設定檔
> - `AndroidManifest.xml`
> 其餘檔案以 Glob 列出路徑即可，不需全部讀取內容。

#### Step 4 — 讀取輸出格式範本
- 讀取 `references/output-format-template.md`

#### Step 5 — 分析與評分
以題目的 `prompt` 作為評分邏輯，結合讀取的原始碼進行分析：

1. **理解題目要求**：從 prompt 中提取功能需求、技術要求、評分標準
2. **逐項檢查**：對照原始碼，逐一檢查每個評分項目
3. **產出報告**：依照 `references/output-format-template.md` 的格式輸出

**評分原則：**
- 客觀、具體：每個評語都要附上程式碼證據（檔名:行號）
- 嚴格遵循 prompt 中的評分標準，不自行發明標準
- 違反事項必須標注 ❌ 並附上 `<檔名:行號>`

#### Step 6 — 輸出報告
依照 `references/output-format-template.md` 格式輸出完整評分報告。

#### Step 7 — 評分後討論迴圈

報告輸出後，**立即**進入討論模式。此迴圈持續進行，直到使用者明確確認完成為止。

**每輪固定詢問：**
```
評分報告已產出。接下來可以：
[1] 調整本次評語或分數（不更新儲存的題目）
[2] 調整並更新題目的評分標準（同時更新儲存的 prompt）
[3] 確認完成評分，結束
請選擇 (1/2/3)：
```

**選 [1] — 調整本次評語或分數：**
1. 詢問：「請描述希望如何調整評語或分數？」
2. 依使用者描述，對現有報告進行修訂，重新輸出**完整**評分報告（嚴格遵循 `references/output-format-template.md` 格式）
3. 回到本迴圈開頭，繼續詢問

**選 [2] — 調整並更新題目的評分標準：**
1. 詢問：「請描述希望如何修改評分標準？（將完整取代題目的 prompt）」
2. 根據使用者描述，**顯示修改後的完整 prompt 草稿**，詢問確認：「是否以此 prompt 更新題目？(y/n)」
3. 使用者確認後，執行：
   ```bash
   python3 $SCRIPT_PATH update --name <name> --prompt - <<'PROMPT_EOF'
   <修改後的完整 prompt 內容>
   PROMPT_EOF
   ```
4. 確認回傳 `"status": "updated"` → 告知更新成功，依新標準重新產出完整評分報告
5. 回到本迴圈開頭，繼續詢問

**選 [3] 或使用者輸入「完成」／「done」／「結束」：**
1. 輸出：「✅ 評分已確認完成。」
2. 結束 Skill

---

### 指令：無參數（互動模式）

1. 執行 `python3 $SCRIPT_PATH list`，以**編號表格**呈現所有題目：
   ```
   | #  | 題目名稱       | 建立時間             |
   |----|----------------|----------------------|
   | 1  | basic-todo-app | 2026-02-05           |
   | 2  | mvvm-weather   | 2026-02-04           |
   ```
2. 若為空 → 詢問是否要新增題目，依回應執行 `add` 流程
3. 否則詢問：
   ```
   請輸入題目編號來選擇題目，或：
   [a] 新增新題目
   [q] 退出
   ```
4. 若輸入**編號**（如 `1`）：
   - 執行 `python3 $SCRIPT_PATH get <name>` 取得題目詳情
   - 顯示題目名稱與 prompt 前 3 行摘要
   - 詢問：
     ```
     選擇操作：
     [1] 評分   [2] 修改 prompt   [3] 刪除   [4] 取消
     ```
   - 依選擇執行對應流程（`grade` / `update` / `delete`）
5. 若輸入 `a` → 執行 `add` 流程
6. 若輸入 `q` → 結束

---

## Output contract（輸出格式保證）
- 所有使用者互動使用**繁體中文**
- 題目管理的操作結果以簡潔文字回報（成功/失敗）
- 評分報告嚴格遵循 `references/output-format-template.md` 格式
- 是/否的詢問一律使用 `(y/n)` 格式

---

## Progressive disclosure map（何時讀/跑什麼）
- 一開始必跑：`scripts/assignment_manager.py`（對應子指令）
- 評分時必讀：題目的 `prompt`、專案原始碼、`references/output-format-template.md`
- 題目管理時不需讀原始碼
