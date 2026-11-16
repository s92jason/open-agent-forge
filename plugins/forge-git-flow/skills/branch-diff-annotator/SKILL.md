---
name: branch-diff-annotator
description: |
  依照當前 git branch 的 diff（HEAD vs branch base），自動為所有新增或修改的函式、方法、類別、屬性加上 docstring，
  並視情況補充行內說明。自動偵測語言，優先遵守專案規範，再套用語言標準（KDoc/JSDoc/PEP 257 等），最後參考現有風格。
  直接修改原始檔案，完成後在對話中輸出摘要報告（不建立額外檔案）。
  當使用者說「幫我加上註解」「補 docstring」「依照 diff 加說明」「幫我補文件說明」「加上符合規範的 docstring」
  「加上符合規範的註解」「依照 branch diff 補文件」時，請使用此 skill。
metadata:
  keywords: "docstring, 註解, comment, diff, branch, KDoc, JSDoc, 文件, annotation, 補文件"
---

# Diff Annotator — 自動為 Branch Diff 加上符合規範的 Docstring

## 目標
對當前 branch 的 diff 中，所有新增或修改的函式、方法、類別、屬性加上 docstring；必要時補充行內說明。直接修改原始檔案，最後在對話中輸出報告。

---

## 執行流程

### Step 1：取得 Diff 範圍

優先使用共用腳本 `$HOME/.claude/skills/shared/scripts/branch_base.py` 解析 branch base，讓本 skill 與其他 branch-diff 系列 skill 共用同一套解析邏輯（自動支援 `BASE_COMMIT` / `BASE_REF` 環境變數覆寫、遠端 ref 防呆等）：

```bash
SHARED_SCRIPTS="$HOME/.claude/skills/shared/scripts"
BASE_INFO=$(python3 "$SHARED_SCRIPTS/branch_base.py" 2>/dev/null)
BASE=$(echo "$BASE_INFO" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('base_commit') or '')" 2>/dev/null)

# Fallback：共用腳本不存在或解析失敗時，改用 git merge-base 本機常見分支
if [ -z "$BASE" ]; then
  BASE=$(git merge-base HEAD main 2>/dev/null \
       || git merge-base HEAD master 2>/dev/null \
       || git merge-base HEAD develop 2>/dev/null)
fi

git diff "$BASE..HEAD"
```

若以上皆失敗（例如非 git repo、或本機沒有 main/master/develop），改用 `git diff HEAD` 作為最後 fallback，並在回報中告知使用者「無法判定 branch base，僅顯示工作區未提交的改動」。

從 diff 中整理：
- 哪些檔案被修改（排除已刪除的檔案）
- 每個檔案中哪些行（`+` 開頭）是新增內容

### Step 2：找出需要補充 docstring 的目標

對每個有改動的檔案：
1. 讀取完整檔案內容
2. 對照 diff 的新增行，定位**新增或修改的函式、方法、類別、屬性宣告**
3. 檢查這些宣告上方是否已有完整的 docstring
4. 若無（或已有但缺少參數說明等重要資訊），加入待處理清單

辨識原則：
- 只處理 diff 中有 `+` 的宣告，不動未改動的程式碼
- 已有完整 docstring 的宣告跳過
- 單行變數/常數：只在用途不明顯時才加行內說明（不是每個都要加）

### Step 3：偵測規範優先順序

依以下順序搜尋規範：
1. **專案規範**：讀取 `CLAUDE.md`、`.claude/`、`docs/` 中有關 coding style 或 docstring 格式的說明
2. **語言標準**：依偵測到的語言套用（見下方「各語言格式」章節）
3. **現有風格**：掃描同一檔案中已有的 docstring 格式，保持一致

### Step 4：撰寫並寫入 Docstring

為每個目標撰寫 docstring，內容應包含：
- **用途說明**：做什麼、為什麼存在（而不是重述函式名稱）
- **Parameters**：每個參數的意義（若有）
- **Return value**：回傳值說明（若有）
- **Throws / Exceptions**：可能拋出的例外（若有）

行內說明只在 WHY 不明顯時加：例如演算法選擇的理由、特殊邊界條件、繞過某個 bug 的原因。不要解釋 WHAT（好的命名本身就是文件）。

用 Edit 工具直接修改原始檔案，保持原有縮排層級。

### Step 5：輸出結果報告

在對話中回覆，格式如下（不建立額外檔案）：

```
## Docstring 加入報告

### 修改檔案

**`path/to/File.kt`**
- `fun fetchUser(id: String)` — 加入 KDoc（說明 DB 查詢邏輯、@param id、@return User?）
- `val retryCount` — 加入行內說明（最大重試次數的業務含義）

**`path/to/ViewModel.kt`**
- `class LoginViewModel` — 加入 KDoc（說明職責與依賴）
- `fun login(email, password)` — 加入 KDoc（@param email/password、@throws AuthException）

### 摘要
共修改 2 個檔案，加入 4 個 docstring、1 個行內說明。
```

---

## 各語言 Docstring 格式

### Kotlin（KDoc）
```kotlin
/**
 * 函式用途說明。
 *
 * @param paramName 參數說明
 * @return 回傳值說明
 * @throws ExceptionType 例外說明
 */
```

### Python（PEP 257 / Google style）
```python
"""函式用途說明。

Args:
    param_name: 參數說明

Returns:
    回傳值說明

Raises:
    ExceptionType: 例外說明
"""
```

### JavaScript / TypeScript（JSDoc）
```javascript
/**
 * 函式用途說明。
 *
 * @param {Type} paramName - 參數說明
 * @returns {Type} 回傳值說明
 * @throws {ErrorType} 例外說明
 */
```

### Java（Javadoc）
```java
/**
 * 函式用途說明。
 *
 * @param paramName 參數說明
 * @return 回傳值說明
 * @throws ExceptionType 例外說明
 */
```

### Swift
```swift
/// 函式用途說明。
///
/// - Parameters:
///   - paramName: 參數說明
/// - Returns: 回傳值說明
/// - Throws: 例外說明
```

### Go
```go
// FuncName 函式用途說明。
// 其他備註或參數說明。
```

---

## 注意事項

- **只動 diff 範圍**：不修改未在本 branch 改動的函式或類別
- **行內說明要克制**：寧可少加，不要過度標記顯而易見的邏輯
- **保持縮排一致**：docstring 縮排必須與宣告相同層級
- **已有 docstring 的處理**：若已有但資訊不完整（例如缺少 @param），可以補充，但保留原有說明文字
