# Code Sync Procedure（程式碼同步流程）

當使用者要在 feature 收尾時，以**目前 working tree 的程式碼為事實基礎**，反向驗證並補完 `FEATURE-SPEC.md` 時使用。

> 此流程同時服務「獨立 Code Sync mode」與「Update mode 菜單 F（現行程式碼局部同步）」：
> - **獨立模式：** 整份 spec sweep，掃所有相關章節，預設範圍為🛠️ 程式影響範圍所列檔案集合。
> - **Update menu F：** 使用者指定的局部檔案 / 資料夾，scope 縮小但流程相同。

## 觸發語

獨立模式典型觸發：
- 「幫我把 spec 對齊 code」
- 「依目前程式碼同步 spec」
- 「feature 收尾要對 spec」
- 「sync spec from code」
- 「程式碼同步模式」

## 與既有 Phase 的關係

Code Sync 流程使用 `CS-1 ~ CS-4` 編號，**不與既有 Phase 1–4 混用**，避免閱讀混淆。

## 階段

### CS-1：Intake

1. **確認既有 spec**：沿用 `operating-procedure.md` Phase 1 Step 2/3 的 Update mode read-first 機制——先請使用者提供 `FEATURE-SPEC.md` 路徑（或自動偵測 repo 內單一檔），讀檔，從第一行 `# Feature Spec: <Name>` 萃取 Feature Name，**不再重問**。
2. **確認掃描範圍**：詢問使用者：

   ```
   要同步的程式碼範圍是？
   A. 沿用 spec🛠️ 程式影響範圍所列檔案（推薦）
   B. 指定 module / 資料夾
   C. 指定檔案 list
   ```

   - 選 A 時，列出🛠️ 程式影響範圍的檔案清單供使用者確認/擴增。
   - 選 B/C 時，使用者直接給路徑。
   - Update menu F 進入本流程時，scope 為使用者已指定的路徑，跳過此步。
3. **檢查 Status**：若 spec `Status:` 為 `Draft` 或 `Pending API confirmation`，提醒使用者「Code Sync 主要用於收尾階段，目前 Status 為 X，是否確認執行？」

### CS-2：Code Scan（read-only）

純 Read 讀取目標檔案集合，萃取以下資訊：

| 萃取項 | 來源（依優先語言：Kotlin / Compose） | 對應 spec 章節 |
|---|---|---|
| API endpoint | Retrofit interface 的 `@GET/@POST/@PUT/@DELETE` 註解、Ktor `client.get/post` 呼叫 | 🔌 API 規格 |
| API request / response 欄位 | data class 屬性、`@SerializedName`、`@Json(name=)` | 🔌 API 規格、附錄 A.2 |
| 頁面 / Composable / Fragment | `@Composable fun XxxScreen()`、`class XxxFragment`、Nav graph route | 🔄 核心流程（頁面清單）、📱 畫面規格 |
| ViewModel state | `StateFlow<XxxState>`、`MutableStateFlow`、`sealed class XxxState` | 📱 畫面規格（狀態表） |
| 業務規則程式段落 | UseCase / Mapper / Domain function 主體 | 📐 業務規則（實作位置） |
| 導頁 / DI / 快取 | `NavController.navigate`、Hilt module、Cache key | 🛠️ 程式影響範圍 |

掃描結果暫存於記憶體，**不寫入任何檔案**。

初版只支援 Kotlin / Compose；其他語言（JS/TS、Swift 等）可於後續版本擴充——目前若偵測到非支援語言，於 CS-3 報告中標示「[語言未支援]」並建議使用者手動補。

### CS-3：Diff Report（必經使用者確認）

**輸出為 read-only 報告，不直接動 spec**。報告分 4 類，每項皆標 `P0 / P1 / P2`：

- **P0**：spec 嚴重失準（不一致、誤導性內容），不修會讓 RD/QA/AI 誤判
- **P1**：spec 不完整（TBD 未回填、缺漏項），補上能提升精準度
- **P2**：spec 過時或冗餘（已被刪除的元件、stale 段落），清理能減少噪音

#### ① TBD 回填（P1）

| spec 章節 | spec 內容（節錄） | code 實際位置 | 建議回填 |
|---|---|---|---|
| 📐 業務規則 → 方案切換規則 | 實作位置: TBD | `FeatureOverviewBlock.kt:L42` | `FeatureOverviewBlock.kt:L42` |

#### ② 缺漏項（P0/P1）

| 類型 | code 中發現 | spec 缺漏的章節 | 建議補充 |
|---|---|---|---|
| 新檔案 | `SpendingFilterRepository.kt` | 🛠️ 程式影響範圍 | 新增至「新增檔案」表 |
| 未列 API | `GET /v3/spending/categories` | 🔌 API 規格 | 新增該 API 子節 |
| 未記載 state | `ErrorWithRetry` state | 📱 畫面規格 → Spending Main → 狀態表 | 新增該 state 列 |

#### ③ 不一致（P0）

| spec 描述 | code 實際 | 衝突類型 | 建議 |
|---|---|---|---|
| 🔌 API 規格 → `chartAggregation` 標為「前端不使用」 | `SpendingViewModel.kt:L88` 確實有讀取 | 標記錯誤 | 改為「前端使用」並補欄位說明 |
| 📐 業務規則 → 規則 R-03「方案 A 顯示 CTA」 | `OverviewBlock.kt:L120` 顯示 CTA 的條件為方案 B | 邏輯不一致 | 追問使用者：以哪邊為準？ |

#### ④ 過時段落（P2）

| spec 章節 | 過時內容 | code 證據 | 建議 |
|---|---|---|---|
| 📱 畫面規格 → 舊版 Filter Dialog | 整段描述 | `FilterDialog.kt` 已被刪除 / 重命名為 `FilterBottomSheet.kt` | 移至附錄 B（歷史與遷移參考）或刪除 |

#### 報告呈現格式

```
🔍 Code Sync Diff Report
範圍：app/src/main/java/.../spending/ （12 個檔案）
spec：FEATURE-SPEC.md（Last Updated: 2026-04-02）

統計：
- ① TBD 回填：5 項（P1）
- ② 缺漏項：3 項（其中 1 項 P0）
- ③ 不一致：2 項（皆 P0）
- ④ 過時段落：1 項（P2）

[每類詳細表格...]

請勾選要套用的項目（可全選 / 部分選）：
- A. 套用全部 P0
- B. 套用全部 P0 + P1
- C. 自訂勾選（請逐項回覆 ID）
- D. 取消，先不改 spec
```

**強制原則：CS-3 一定 read-only，使用者明確選 A/B/C 之前不得動 `FEATURE-SPEC.md`。**

### CS-4：Apply（依使用者勾選寫回）

1. **逐項套用**使用者勾選的項目，修改對應章節。
2. **更新 metadata**：
   - 文件頭部 `Last Updated:` 改為當日日期。
   - 若所有 pending（含 ❓ 待確認事項與 [Pending] 標記）均已解決 → `Status:` 可提升至 `Ready`；否則維持 `In Progress`。
3. **附錄 C Change Log 追加一筆**：

   ```
   | 日期 | 變更摘要 |
   |------|----------|
   | 2026-05-14 | 程式碼同步更新：回填 5 項實作位置、補 3 個欄位/檔案、修正 2 處不一致 |
   ```

4. **未勾選項目處理**：
   - P0 不一致未勾選 → 加入 ❓ 待確認事項，標 `[Pending] code 與 spec 不一致，等待人工裁決`。
   - 其他未勾選 → 不動，但於對話末尾提醒「以下 N 項本次未處理」，供使用者下次補。
5. **不執行 Phase 3.5 Post-Draft Q&A**：Code Sync 已經是事實核對，再做 Q&A 會冗餘。但仍跑 **Phase 4 Validate** 確保整體結構完整。

## 與 Update mode F 的執行差異

| 面向 | 獨立 Code Sync mode | Update menu F |
|---|---|---|
| Scope | 整份 spec / 整套 code | 使用者指定的局部路徑 |
| CS-1 | 完整 intake（含範圍選單 A/B/C） | 跳過範圍選單，沿用 F 階段已給的路徑 |
| CS-2 | 全掃 | 局部掃 |
| CS-3 | 完整 4 類報告 | 僅輸出與指定路徑相關的項目 |
| CS-4 | 完整 apply + Phase 4 Validate | 套用後回 Update menu，等使用者選 H 才跑 Phase 4 Validate |
| Change Log | 「程式碼同步更新」 | 「局部同步更新（路徑：xxx）」 |

## 失敗處理

- **無 `FEATURE-SPEC.md`**：拒絕進入，提示使用者改用 Create mode。
- **掃描範圍空**（使用者給的路徑不存在）：報錯並請使用者修正。
- **語言不支援**：CS-3 報告中標示「[語言未支援]」，使用者可自行對應補 spec。
- **CS-3 報告為空（無任何差異）**：直接告知「spec 已與 code 同步」，不進 CS-4，不動 Change Log。
