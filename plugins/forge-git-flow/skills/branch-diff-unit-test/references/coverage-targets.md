# Coverage Targets — 覆蓋率目標分級

## 目標分級

### 必須達到 90%+（業務邏輯核心）
| 類型 | 說明 | 優先級 |
|------|------|--------|
| ViewModel | 狀態機、UI 事件處理、資料轉換 | ★★★ |
| UseCase / Interactor | 業務規則、輸入驗證、資料組合 | ★★★ |
| Repository | 資料策略（cache/remote/local）、錯誤處理 | ★★★ |
| Handler | 事件處理、訊息路由 | ★★★ |
| Presenter | 視圖狀態計算、資料格式化 | ★★★ |

### 盡力覆蓋（複雜邏輯才補）
| 類型 | 補充條件 |
|------|---------|
| Service | 有明顯業務邏輯分支時 |
| Manager | 有狀態管理時 |
| Mapper / Converter | 有複雜欄位轉換或特殊邏輯時 |
| Extension functions | 在業務邏輯 diff 中新增時 |

### 可適度放寬（不需達到 90%）
| 類型 | 原因 |
|------|------|
| DI Module（Hilt/Dagger） | 主要是 binding 宣告，無邏輯分支 |
| Data class / Model | 純資料容器，`equals`/`copy` 由編譯器生成 |
| Entity（Room） | 資料庫結構定義，由框架處理 |
| 抽象基底類別 | 子類別測試時會覆蓋 |
| sealed class 本身 | 各分支由具體測試覆蓋 |

---

## 自評估方法論

### Branch 計數規則

計算「已覆蓋分支數 / 總分支數」（branch coverage）：

**計入**（需計算分支）：
- `if/else`：true 路徑與 false 路徑各算一個分支
- `when`：每個 arm（含 `else`）各算一個分支
- `try/catch`：正常路徑與每個 catch block 各算一個分支
- `?:` Elvis 運算子：非 null 路徑與 null fallback 路徑各算一個分支
- `&&`／`||` 短路求值：兩個 operand 各自為 true/false 的路徑
- `for`／`while`：迴圈執行（至少一次）與跳過（零次）各算一個分支

**不計入**（可略過）：
- 無條件語句（單純賦值、log、回傳常數）
- 純 getter/setter（無邏輯，只回傳欄位）
- Override 自 framework（如 `onCreate`、`onCleared`）——除非有自訂邏輯
- 繼承的 sealed class 結構宣告本身（各 arm 由具體測試覆蓋）

### 覆蓋標準

一個分支「被覆蓋」的條件（至少滿足其一）：
1. 有 test case 讓該分支的條件為 true，且執行了 true 路徑
2. 有 test case 讓該分支的條件為 false，且執行了 false/else 路徑
3. 分支被其他被測試路徑間接觸及（需明確記錄）

### 例外情況記錄格式

```
| UserViewModel.observeLocationUpdates | 未覆蓋 | LocationManager 依賴難以在 unit test 環境中 mock，需要 Instrumentation test |
```

---

## 低於 90% Branch Coverage 的可接受情形

| 情形 | 可接受最低 Branch Coverage | 說明 |
|------|--------------------------|------|
| 大量 framework callback | 70% | 如 `onResume`、`onDestroy` 等 Android lifecycle，分支多但難以控制 |
| 高複雜度 DI 整合 | 75% | 依賴鏈深度超過 3 層，部分 else 分支難以在 unit test 環境觸發 |
| 混合 Java/Kotlin 遺留程式碼 | 75% | 舊版 Java 類別難以 mock，部分分支無法有效隔離 |
| 單一用途的 Mapper 類別 | 80% | 若欄位映射超過 10 個，可只測有條件轉換的代表性分支 |

**不可接受的例外**（無論如何都必須補）：
- 金流、支付、帳戶餘額相關邏輯
- 登入驗證、授權邏輯
- 資料加解密邏輯
- 狀態機的每個轉移
