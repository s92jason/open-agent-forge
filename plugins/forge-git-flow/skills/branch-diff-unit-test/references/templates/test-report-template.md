# Unit Test Report Template

<!-- 最終報告輸出格式。填入實際值並移除 HTML 註解。 -->

## Unit Test 報告

### 測試範圍

| 欄位 | 值 |
|------|---|
| 分支 | `<branch-name>` |
| Base Ref | `<base-ref>` |
| Base Commit | `<base-commit-sha>` |
| HEAD | `<head-commit-sha>` |
| 分析原始檔案數 | N 個 |
| 產生測試檔案數 | M 個 |

---

### 寫入的測試檔案

```
src/test/kotlin/com/example/feature/UserViewModelTest.kt       [新建]
src/test/kotlin/com/example/domain/GetUserUseCaseTest.kt       [新建]
src/test/kotlin/com/example/data/UserRepositoryImplTest.kt     [更新：新增 3 個 test case]
```

---

### 主要測試情境（依覆蓋情境分組）

<!-- 每個類別列出 2–5 個情境，以功能分組而非逐一列舉方法 -->

**UserViewModel**
- 初始狀態與登入觸發流程（happy path）
- 網路錯誤與 Loading 狀態轉換
- Null 輸入與邊緣條件處理
- 多個連續請求的狀態覆蓋

**GetUserUseCase**
- 合法輸入的成功業務流程
- 空白 / null 輸入的輸入驗證
- Repository 異常傳播行為

**UserRepositoryImpl**
- Cache-first 策略：命中與未命中
- 網路失敗的 fallback 行為
- 資料儲存（saveUser）的副作用驗證

---

### Branch Coverage

<!-- 量測方式欄位填入：估算 / Gradle (JaCoCo) / Gradle (Kover) -->

| 類別 | 類型 | 量測方式 | 總 Branches | 已覆蓋 | Branch Coverage | 備註 |
|------|------|---------|------------|--------|----------------|------|
| UserViewModel | ViewModel | Gradle (JaCoCo) | 10 | 10 | 100% | — |
| GetUserUseCase | UseCase | Gradle (JaCoCo) | 4 | 4 | 100% | — |
| UserRepositoryImpl | Repository | 估算 | 8 | 6 | 75% | `observeChanges()` 依賴 Flow channel，難以在 unit test 中驗證時序 |

**整體 Branch Coverage（加權平均）**：`90.9%` ✓（目標 ≥ 90%）

---

### 未覆蓋部分與原因

| 方法 | 類別 | 原因 |
|------|------|------|
| `observeChanges()` | UserRepositoryImpl | 依賴 Room Database Flow，需 Instrumentation Test 才能驗證 |

---

### 建議後續補充

<!-- 若有，列出建議；若無，刪除本節 -->

- [ ] `UserRepositoryImpl.observeChanges()` — 建議補充 Integration Test（使用 Room in-memory database）
- [ ] `UserViewModel.handleDeepLink()` — 此方法在本次 diff 未改動，建議在後續重構時一併補充測試
