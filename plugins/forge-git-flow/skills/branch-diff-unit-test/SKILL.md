---
name: branch-diff-unit-test
description: |
  依照當前 git branch 的 diff，自動分析並為新增或修改的業務邏輯類別
  （ViewModel、UseCase、Repository、Handler、Presenter 等）補充 Unit Test。
  遵照 Android 測試最佳實踐（JUnit4/5 + MockK + Coroutines），目標 branch coverage 90%+，
  支援參考文件設定的記憶與調整，最終輸出測試摘要報告。
allowed-tools: Bash(git:*) Bash(python3:*) Bash(find:*) Bash(grep:*) Bash(mkdir:*) Bash(ls:*) Bash(./gradlew:*) Read Edit Write
metadata:
  keywords: "unit test, 單元測試, test, 測試, Android, ViewModel, UseCase, Repository, Handler, Presenter, branch, diff, 補測試, 加測試, 寫測試, coverage, 覆蓋率"
  user-invocable: "true"
---

# Branch Diff Unit Test Skill

## Trigger cues
當使用者出現以下意圖，啟用本 Skill：
- 「幫我補 unit test」
- 「幫我寫測試」
- 「補充單元測試」
- 「依照這次分支改動加測試」
- 「幫我為這個 branch 的改動補 test」
- 直接輸入 `/branch-diff-unit-test`

## Non-trigger cues
以下情境不要啟用：
- 使用者只問如何寫測試（一般問答即可）
- 只想 review code（改用 `/branch-diff-code-review`）
- 不在 git repo 內
- 目標是 E2E/UI 自動化測試（本 skill 只處理 Unit Test）

---

## Operating procedure（流程）

### Step 0 — 環境前置檢查（必做）

執行以下檢查，任一失敗則說明原因並終止：

```bash
# 確認在 git repo 內
git rev-parse --is-inside-work-tree

# 確認當前分支不是 main / master
CURRENT_BRANCH=$(git branch --show-current)
# 若 CURRENT_BRANCH 為 main 或 master，終止並警告

# 找出 branch base
SHARED_SCRIPTS="$HOME/.claude/skills/shared/scripts"
BASE_INFO=$(python3 "$SHARED_SCRIPTS/branch_base.py" 2>/dev/null)
# 若失敗，回退至：
BASE=$(git merge-base HEAD main 2>/dev/null || git merge-base HEAD master 2>/dev/null || git merge-base HEAD develop 2>/dev/null)

# 確認有 branch diff
CHANGED_FILES=$(git diff --name-only $BASE..HEAD | wc -l | tr -d ' ')
# 若 CHANGED_FILES 為 0，終止並提示沒有需要補測試的改動
```

確認通過後，輸出確認畫面並**暫停等待使用者確認**：

```
## Branch Diff Unit Test — 確認目標

  當前分支：<branch-name>
  合併基準：<base-ref> (<base-short-sha>)
  異動檔案：<N> 個（含 src 與 test）
  HEAD commit：<head-short-sha> <head-commit-subject>

即將為此分支的業務邏輯改動補充 Unit Test。

確認以上分支資訊正確，開始補測試流程？(y/n)
```

---

### Step 1 — 取得 Diff 範圍並識別測試目標

```bash
git diff --name-only $BASE..HEAD
```

**排除以下類型**（不需補測試，或已是測試）：
- `*Test*.kt`、`*Test.java`、`*Spec.kt` — 已是測試檔
- `build/`、`*.gradle`、`*.gradle.kts` — 建置設定
- `*.xml`、`res/`、`*.json`（非業務邏輯）— 資源檔
- `generated/`、`build/generated/` — 自動產生
- `*.md`、`*.txt`、`*.properties` — 文件與設定

**識別業務邏輯目標檔案**（依以下優先順序）：

| 類型 | 命名特徵 | 優先級 |
|------|---------|--------|
| ViewModel | `*ViewModel.kt` | 最高（必須覆蓋） |
| UseCase / Interactor | `*UseCase.kt`、`*Interactor.kt` | 最高（必須覆蓋） |
| Repository | `*Repository.kt`、`*Repo.kt` | 最高（必須覆蓋） |
| Handler / Presenter | `*Handler.kt`、`*Presenter.kt` | 高（優先覆蓋） |
| Service / Manager | `*Service.kt`、`*Manager.kt` | 中（視複雜度） |
| Mapper / Converter | `*Mapper.kt`、`*Converter.kt` | 中（視複雜度） |
| Model / Entity | `*Model.kt`、`*Entity.kt` | 低（一般跳過） |

輸出分類清單，並說明哪些會補測試、哪些略過（附理由）。

**建立 TARGET_CLASSES 清單**（供後續步驟共用，避免重複執行 git 指令）：

將每個目標檔案的路徑轉換為三種格式並記錄：

| 原始路徑 | Gradle module（用於 task 前綴） | JaCoCo class name（用於篩選報告） | Gradle test class（用於 --tests 旗標） |
|---------|------------------------------|--------------------------------|--------------------------------------|
| `app/src/main/kotlin/com/example/UserViewModel.kt` | `:app` | `com/example/UserViewModel` | `com.example.UserViewModelTest` |
| `feature/user/src/main/kotlin/com/example/data/UserRepository.kt` | `:feature:user` | `com/example/data/UserRepository` | `com.example.data.UserRepositoryTest` |
| `src/main/kotlin/com/example/Foo.kt`（單模組） | `""`（無前綴） | `com/example/Foo` | `com.example.FooTest` |

轉換規則：
- **Gradle module**：從專案根目錄起算，取到 `src/main/{kotlin,java}` 之前的路徑段；把分隔符 `/` 換成 `:`、開頭補 `:`；若目標檔案就在根目錄的 `src/main/` 下（單模組專案），module 留空字串。
  - 可信度檢查：對應 module 路徑下應有 `build.gradle` 或 `build.gradle.kts`；若無，往上一層繼續找直到找到為止；都找不到則記錄為「無法推導」並退回估算模式提示。
- **JaCoCo class name**：去除 `<module>/src/main/{kotlin,java}/` 前綴，去除 `.kt` / `.java` 副檔名
- **Gradle test class**：同上，再將 `/` 替換為 `.`，附加 `Test` 後綴

TARGET_CLASSES 清單在整個 Skill 執行過程中保持不變，Step 4～6 直接引用，**不需重跑任何 git 指令**。

若無任何符合目標 → 顯示提示並結束：
```
✓ 本次 diff 中沒有發現需要補 Unit Test 的業務邏輯檔案。
```

---

### Step 2 — 參考文件設定管理（含持久化）

**設定檔位置**：
```bash
SETTINGS_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/claude-forge/branch-diff-unit-test"
PROJECT_KEY=$(git rev-parse --show-toplevel | xargs basename | tr -cs 'a-zA-Z0-9_-' '_')
SETTINGS_FILE="$SETTINGS_DIR/${PROJECT_KEY}.json"
```

**互動邏輯**：

**若設定檔存在**（用 Read tool 讀取）：
```
## 參考文件設定（已有儲存設定）

  參考文件：<reference_files list or "無">
  自訂說明：<custom_notes or "無">
  覆蓋率目標：<coverage_target>%
  上次更新：<last_updated>

請選擇：
[1] 延續現有設定（繼續）
[2] 更新設定（重新輸入）
[3] 清除設定（從頭開始）
```

**若設定檔不存在**：
```
## 參考文件設定（首次使用）

此專案尚未設定測試參考文件。

是否有測試規範文件或自訂參考資料？
（例如：/path/to/testing-guide.md 或輸入 n 略過）
```

**儲存 / 更新設定**：Claude 用 Write tool 寫入 JSON：
```json
{
  "reference_files": [],
  "custom_notes": "",
  "coverage_target": 90,
  "last_updated": "<YYYY-MM-DD>"
}
```

若用戶選擇清除：`Bash rm "$SETTINGS_FILE"`，然後重新詢問。

---

### Step 3 — 分析測試目標

對每個目標檔案（用 `Read` tool 讀取完整原始碼）：

1. **識別 public method / function 清單**
   - Kotlin：`fun`（非 `private`、非 `internal`）
   - 包含 companion object 方法
   - 包含 operator fun（`invoke`、`get` 等）

2. **識別依賴項與 mock 需求**
   - constructor 注入的類別 → 需要 mock
   - `@Inject` 欄位 → 需要 mock
   - 靜態呼叫（object、companion）→ 可能需要 mockStatic

3. **識別邊緣情況**
   - nullable 參數（`?` 型別）
   - sealed class / enum 分支（when expression）
   - suspend function → 需要 `runTest`
   - Flow 回傳型別 → 需要 Turbine 或 collect
   - Exception 拋出點（`throw`、`try/catch`）
   - 空列表 / 空字串輸入

4. **若有參考文件**：Read tool 讀取，套用自訂規範

5. 輸出「測試分析摘要」：
   ```
   ## 測試分析摘要

   **UserViewModel.kt**（ViewModel）
   - public methods：5 個（loadUser、saveUser、deleteUser、resetState、handleError）
   - 依賴：UserRepository（需 mock）、Dispatchers（需 TestDispatcher）
   - 邊緣情況：loadUser 有 null 回傳、handleError 有 3 種 sealed class
   - Coroutines：3 個 suspend fun，1 個 StateFlow
   ```

---

### Step 4 — 產生 Unit Tests（核心步驟）

參考 `references/android-testing-guidelines.md` 和 `references/test-patterns.md`。

**測試檔案位置規則**：
```bash
# 從 production 路徑推導 test 路徑：
# src/main/kotlin/com/example/UserViewModel.kt
# → src/test/kotlin/com/example/UserViewModelTest.kt
```

若測試檔案不存在 → 用 Write tool 建立（含 package 宣告）。
若測試檔案已存在 → 用 Edit tool 新增 test case（避免覆蓋現有測試）。

**框架慣例**（依偵測結果選用，詳見 `references/android-testing-guidelines.md`）：
- MockK（Kotlin 專案優先）
- JUnit4 `@RunWith(JUnit4::class)` 或 JUnit5 `@ExtendWith(MockKExtension::class)`
- Coroutines：`@OptIn(ExperimentalCoroutinesApi::class)` + `runTest` + `UnconfinedTestDispatcher`
- StateFlow/LiveData：`InstantTaskExecutorRule`（JUnit4）或 `@get:Rule`

**強制覆蓋清單**（業務邏輯，目標 branch coverage ≥ 90%）：

| 情境 | 測試需求 |
|------|---------|
| 每個 public method | ≥ 1 happy path |
| 每個 error/exception path | ≥ 1 test case |
| sealed class / when 每個 branch | ≥ 1 test case |
| state machine 每個轉移 | ≥ 1 test case |
| nullable 參數 | null 值輸入的 test case |
| Flow / StateFlow emission | 發射序列的 test case |

**UI 邏輯判斷**：
- StateFlow 有複雜轉換邏輯（多層 map/filter/combine）→ 補充 state 變化測試
- 純 pass-through assignment → 可略過

**覆蓋率調整**：
- 若類別有大量 framework callback（如繼承 `BaseViewModel` 抽象方法）→ 可調低至 70%，需在報告記錄原因
- 若類別有複雜 DI 設定 → 記錄難以測試的部分

**測試命名規範**（參考 `references/test-patterns.md`）：
```kotlin
// 格式：`fun <methodName>_<scenario>_<expected>()`
@Test
fun `loadUser_whenIdIsNull_returnsError`() { ... }

@Test
fun `saveUser_withValidData_updatesState`() { ... }
```

---

### Step 4.5 — 後續處理模式選擇

測試檔案寫入完成後，詢問使用者：

```
## 後續處理方式

測試已寫入。請選擇後續處理：
[1] 📊 估算模式（Estimation）— Claude 靜態分析 branch coverage，不執行任何指令
[2] ⚡ Gradle 快速模式（Tests Only）— 執行 ./gradlew --tests 確認新測試通過，不算 coverage
[3] 🚀 Gradle 完整模式（Tests + Coverage）— 執行測試並產生 JaCoCo/Kover 報告，取得精確 branch coverage

⚠️ 模式 [3] 會觸發 jacocoTestReport / koverXmlReport，這兩個任務的設計是
   「掃描整個 module 的所有 class」，無法用 --tests 限制範圍——
   即使只有少量檔案異動，報告階段仍會耗時，請斟酌選擇。
```

**若選擇 [2] 或 [3]**，立即執行 Gradle 環境可行性檢查：

```bash
# 確認 ./gradlew 存在
ls ./gradlew 2>/dev/null

# 自動偵測 test task 名稱（依序嘗試，搭配 TARGET_CLASSES 中的 module 前綴）：
# 1. testDebugUnitTest（Android 標準）
# 2. test（純 JVM module）
# 若以上皆無法確認，詢問使用者提供 task 名稱
# 注意：實際組成的指令會是 :module:testDebugUnitTest（見 Step 5-B ①）

# 模式 [3] 額外偵測覆蓋率報告任務（依序嘗試）：
# 1. jacocoTestReport
# 2. jacocoDebugTestReport
# 3. koverXmlReport
# 4. koverXmlReportDebug

# 覆蓋率報告 XML 預期路徑（依任務名稱對應）：
# build/reports/jacoco/<task-name>/<task-name>.xml
# build/reports/kover/report.xml 或 build/reports/kover/reportDebug.xml
```

**若環境不可行**：
- `./gradlew` 不存在：說明原因，**自動切換為估算模式 [1]**
- 模式 [3] 但找不到任何覆蓋率報告任務：說明原因，**自動降級為模式 [2]**（仍跑測試），或詢問是否退回 [1]

---

### Step 5 — Branch Coverage 量測

依 Step 4.5 選擇的模式執行：

---

#### Step 5-A — 估算模式（靜態分析）

對每個被測試的類別：

1. 列出所有條件分支（`if/else`、`when`、`try/catch`、`?:`、`&&`/`||` 短路等）
2. 標記每個分支是否有 test case 覆蓋其 true/false（或各個 `when` arm）路徑
3. 計算：`branch_coverage = covered_branches / total_branches × 100%`
4. 整體覆蓋率 = 加權平均（依分支總數）

標記**無法輕易達到 90%** 的例外（記錄原因）：
- Framework callback（繼承而來的 override）
- Abstract interface delegation
- DI module / Hilt 相關
- 第三方 SDK 的 callback

---

#### Step 5-B — Gradle 模式（實際執行）

> **模式 [2] 快速模式**：只執行下方步驟 ①，跑完取得 PASS/FAIL 後直接進入 Step 6（不算 coverage、不迭代補強）。
> **模式 [3] 完整模式**：依序執行 ① → ①.5 → ② → ③ → ④ → ⑤，**最多 2 輪迭代**。

**① 執行 Gradle test（兩模式共用）**：

從 TARGET_CLASSES 取出**所有不重複的 Gradle module**（AFFECTED_MODULES），為每個 module 組合 `:module:<test-task>` 作為 Gradle target，並把 Gradle test class 全部塞到一組 `--tests` 旗標：

```bash
# 範例：AFFECTED_MODULES = [":app", ":feature:user"]
./gradlew \
  :app:testDebugUnitTest \
  :feature:user:testDebugUnitTest \
  --tests "com.example.UserViewModelTest" \
  --tests "com.example.data.UserRepositoryTest" \
  2>&1
```

> **必須**為每個 affected module 加上 `:module:` 前綴；若使用裸 task（例如只寫 `testDebugUnitTest`），
> Gradle 會在每個註冊了該 task 的 module 上都嘗試執行，多模組專案會顯著拖慢編譯。
> 單模組專案（module 欄位為空字串）才使用裸 task。
> 若 Step 3 分析時發現測試類別名稱與 production class 名稱不同
> （例如 `LoginHandlerImpl` 對應的測試是 `LoginHandlerTest`），請使用實際存在的 test class 名稱。

**若選擇模式 [2] 快速模式 → 跳到 Step 6**，僅在最終報告標示「Gradle 快速模式：N 個測試類別、X 通過 / Y 失敗」，不需要 coverage 表格。

---

**①.5 觸發覆蓋率報告任務（僅完整模式需要）**：

對每個 affected module 套用前綴執行 report 任務，任務名稱用 Step 4.5 偵測到的結果（依序嘗試）：

```bash
# 範例：AFFECTED_MODULES = [":app", ":feature:user"]
./gradlew \
  :app:jacocoTestReport \
  :feature:user:jacocoTestReport
```

任務名稱偵測順序：
1. `jacocoTestReport`（JaCoCo 標準）
2. `jacocoDebugTestReport`（部分 Android 專案）
3. `koverXmlReport` / `koverXmlReportDebug`（Kover）

若全部任務都不存在 → 提示「專案未配置 JaCoCo/Kover 報告任務」，**自動降級為模式 [2] 快速模式**（保留 ① 結果）。

> ⚠️ 此任務無法用 `--tests` 過濾範圍，會掃描整個 module 內所有 class 與 source files。
> 這是 JaCoCo / Kover 的架構性設計，skill 無法縮短此階段的執行時間；
> 加上 `:module:` 前綴可以避免「在無關 module 也跑一次 report」造成的加倍成本。

**② 讀取覆蓋率報告**：

> ⚠️ 此步驟使用 **Step 1 已建立的 TARGET_CLASSES 清單（JaCoCo class name 欄位）** 來篩選報告內容，
> 不需要也不應執行任何 git 指令（包含 `git fetch`、`git diff`、`git log` 等）。
> 報告產生本身的耗時無法縮短，但解析只需處理少量目標 class，因此 Read 階段很快。

用 Read tool 讀取每個 affected module 對應的 JaCoCo XML（或 Kover XML），依 TARGET_CLASSES 的 JaCoCo class name 定位目標類別的 branch 資料：

```xml
<!-- JaCoCo 格式 -->
<class name="com/example/UserViewModel">
  <counter type="BRANCH" missed="2" covered="8"/>
</class>
```

計算：`branch_coverage = covered / (missed + covered) × 100%`

**③ 識別覆蓋率缺口**：
- 列出 coverage < target（預設 90%）的 class
- 記錄各 class 的 missed branches 數量

**④ 補強測試（若有缺口）**：
- 針對 missed branches 用 Edit tool 新增對應 test case
- 新增的 test 加上行內標記 `// [Gradle 補強]` 便於識別

**⑤ 若有補強 → 重新執行 ① + ①.5（最多再 1 次）**：

終止條件（滿足任一即停止）：
- coverage ≥ target
- 改善幅度 < 3%（剩餘 missed branches 為 framework/abstract，無法進一步補強）
- 已達迭代上限（第 2 輪）

**若 Gradle 執行失敗**（編譯錯誤、測試崩潰）：
- 顯示錯誤摘要（前 30 行）
- 詢問是否退回估算模式繼續（Step 5-A）

---

### Step 6 — 輸出最終報告

依 `references/templates/test-report-template.md` 格式輸出。報告格式依 Step 4.5 選擇的模式略有不同：

**模式 [1] 估算 / 模式 [3] Gradle 完整 — 含 Coverage 表格**

1. **測試範圍**：branch、base ref/commit、HEAD、分析的原始檔案數
2. **寫入的測試檔案**：完整路徑清單
3. **主要測試情境**（依情境分組，非逐一列舉）：
   ```
   UserViewModel → 登入成功流程 / 錯誤狀態處理 / Loading 狀態轉換 / Null 輸入邊緣情況
   UserRepository → 網路成功回傳 / 網路失敗 fallback 至 cache / 空資料回傳
   ```
4. **Branch Coverage 表格**（含量測方式欄位）：

   | 類別 | 量測方式 | 總 Branches | 已覆蓋 | Branch Coverage | 備註 |
   |------|---------|------------|--------|----------------|------|
   | UserViewModel | Gradle (JaCoCo) | 12 | 12 | 100% | — |
   | UserRepository | 估算 | 8 | 6 | 75% | cache 策略的 2 個 else 分支難以隔離測試 |

   量測方式可填：`估算`、`Gradle (JaCoCo)`、`Gradle (Kover)`

5. **整體 Branch Coverage**：加權平均（依分支總數）
6. **未覆蓋部分與原因**（若有）
7. **建議後續補充**（若有）

**模式 [2] Gradle 快速模式 — 僅測試結果，無 Coverage**

1. **測試範圍**：同上
2. **寫入的測試檔案**：完整路徑清單
3. **執行模式聲明**：`Gradle 快速模式（Tests Only，未量測 Branch Coverage）`
4. **測試執行結果**：

   | Module | 測試類別 | 測試方法數 | 通過 | 失敗 | 備註 |
   |--------|---------|----------|------|------|------|
   | `:app` | UserViewModelTest | 12 | 12 | 0 | — |
   | `:feature:user` | UserRepositoryTest | 8 | 7 | 1 | `getUser_whenNetworkFail_returnsCache` 失敗 |

5. **失敗測試詳情**（若有）：列出失敗的測試方法與簡短錯誤摘要
6. **建議後續補充**：若想取得 Branch Coverage，重新執行並選擇模式 [1] 或 [3]

---

## Progressive disclosure map

- Android 測試框架選用準則 → `references/android-testing-guidelines.md`
- 覆蓋率目標分級與自評方法 → `references/coverage-targets.md`
- 常用測試模式與程式碼模板 → `references/test-patterns.md`
- 最終報告固定格式 → `references/templates/test-report-template.md`

---

## Error handling

| 情境 | 處理方式 |
|------|---------|
| `shared/scripts/branch_base.py` 不存在 | 回退至 `git merge-base HEAD main/master/develop` |
| 找不到 `src/test/kotlin/` 目錄 | 用 `find` 搜尋 test source set，或提示使用者確認路徑 |
| 目標檔案使用不支援的語言 | 跳過並記錄，繼續處理其他檔案 |
| 測試檔案已存在且有內容 | 只追加新 test case，不覆蓋現有測試 |
| Branch 為 main/master | 終止並警告：請先建立 feature branch |
| `./gradlew` 不存在（Gradle 模式） | 告知原因，自動切換為估算模式 |
| 找不到 JaCoCo/Kover 報告任務（Gradle 完整模式） | 告知原因，**自動降級為 Gradle 快速模式 [2]**；若使用者要求 coverage，再退回估算模式 [1] |
| Gradle 執行失敗（編譯/測試崩潰） | 顯示錯誤前 30 行，詢問是否退回估算模式 |
| Step 5 中出現 git fetch / git diff 等 git 操作 | 這是異常行為，應立即停止並改用 Step 1 的 TARGET_CLASSES 清單 |
| TARGET_CLASSES 推導出的 test class 名稱不存在 | 略過該 `--tests` 旗標，改用 wildcard（`com.example.*Test`），並在最終報告記錄 |
| 無法從檔案路徑推導 Gradle module | 提示使用者確認 module 結構；若仍無法解析，該 class 改以無前綴執行並在報告標註，或建議退回估算模式 |
| 多 module diff，部分 module 沒有對應測試類別 | 該 module 的 `--tests` 旗標可省略（但 task target 仍保留以觸發編譯）；在最終報告標示「未找到測試類別」 |
| AFFECTED_MODULES 包含同名 task 但 variant 不同（例如 `:app:testDebugUnitTest` vs `:lib:testReleaseUnitTest`） | 以該 module 實際存在的 task 為準；若混雜，分批執行兩種 task name |
