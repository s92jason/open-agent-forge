# Update Mode Menu

Update mode 採用「菜單式」流程，**不再沿用 Create mode 的順序式 intake**。使用者依本次需求挑選要更新的面向，可多次循環，明確選 `H` 才結束。

## 何時進入此流程

當 Phase 1 偵測到既有 `FEATURE-SPEC.md` 且使用者選擇 Update mode 時，**跳過 Create mode 的 Step 4–6 順序式詢問**，改走本菜單。

設計原則：
- 使用者只想動哪幾項，就只問哪幾項。
- 任何未被選到的章節，本次不重寫、不重 Reconcile，避免暴力覆蓋既有內容。
- 菜單呈現允許「一次列出選項」，不違反 Phase 1「一次只問一個問題」原則——選項是動作分類，使用者選擇後才開始該分支的逐項問答。

## 進入菜單前的準備

1. **讀取既有 spec**：依 Phase 1 Step 2/3 的 Update mode 順序，先請使用者提供 `FEATURE-SPEC.md` 路徑（或自動偵測 repo 內單一檔），讀檔。
2. **萃取 metadata**：從第一行 `# Feature Spec: <Name>` 取 Feature Name；同步讀 `Status:` / `Last Updated:` / `Mode:`。
3. **掃描章節**：建立章節索引（哪些章節存在、❓ 待確認事項數量、🔌 API 規格有幾支 API、📐 業務規則「實作位置: TBD」剩幾項）。
4. **顯示摘要**（範例）：

   ```
   偵測到既有 spec：Spending Analysis Revamp
   路徑：app/src/main/java/.../spending/FEATURE-SPEC.md
   Status：In Progress
   Last Updated：2026-04-02
   待確認事項：3 項
   API 規格：4 支（其中 1 支標 [Pending]）
   📐 實作位置 TBD：5 項
   ```

5. **跳過 Feature Name 詢問**（修正 1）。若萃取失敗（檔頭缺漏 `# Feature Spec: <Name>`），fallback 詢問 Feature Name 並提醒使用者修補檔頭。

## 菜單

```
本次要更新哪些內容？（可多次選擇，完成後選 H）
A. Axure 補充 / 修改
B. Figma 補充 / 修改
C. API 規格補充 / 修改
D. 回答待確認事項
E. 自行補充事項（使用者直接提供文字）
F. 現行程式碼局部同步（指定檔案 / 資料夾）
G. 其他（自行描述，由 skill 判斷影響範圍）
H. 結束並進入 Reconcile
```

## 各選項子流程

### A. Axure 補充 / 修改

1. 詢問：「請提供 Axure link。」
2. 多輪收集，沿用「完成 / 沒了 / done」終止語（與 `operating-procedure.md` Phase 1 Step 5 一致）。**本輪收齊的 URL 加入本次 Update 的待抓清單，不在此 step 呼叫 wrapper**。
3. 標記受影響章節：🔄 核心流程、📱 畫面規格（凡新 Axure 提及的頁面/分支）、❓ 待確認事項（若 Axure 解決了原本的 pending）。**收齊就標記，不等抓取結果**——使用者已宣告 intent，即使後續抓取失敗或被略過個別 URL，章節仍視為 touch。
4. 結束後回菜單。**實際 wrapper 抓取一律延後到 H 觸發**（A 累積的 URL 屆時必加 `--bust-cache`：使用者在 A 重列 URL 即表示要 refetch，規則見 `cache-policy.md`）。

### B. Figma 補充 / 修改

1. 詢問：「請提供 Figma link（file / page / frame 皆可）。」
2. 多輪收集，沿用「完成 / 沒了 / done」終止語。**本輪收齊的 URL 加入本次 Update 的待抓清單，不在此 step 呼叫 wrapper**。
3. 標記受影響章節：📱 畫面規格（最主要）、🔄 核心流程（頁面清單若有新增）。同樣「收齊就標記，不等抓取結果」。
4. 結束後回菜單。**實際 wrapper 抓取一律延後到 H 觸發**（B 累積的 URL 屆時必加 `--bust-cache`；token 由底層 extractor 自動從 Keychain 讀取）。

### C. API 規格補充 / 修改

1. 詢問：「請提供第一份 API 文件（連結或內容）。」
2. 多輪收集，沿用「完成 / 沒了 / done」終止語（與修正 2 對齊：Create mode 也改多輪）。
3. 標記受影響章節：🔌 API 規格、附錄 A.1/A.2（型別定義）、📱 畫面規格（資料來源段落需更新 API 名稱）。
4. 結束後回菜單。

### D. 回答待確認事項

1. 讀現有 spec 的 `❓ 待確認事項` 章節，逐項列出。
2. 對每一項：顯示問題 → 等待使用者答覆 → 答案回寫對應章節 → 從 ❓ 待確認事項移除。
3. 全部處理完或使用者說「先處理到這裡」即結束本選項。
4. 若全部 pending 被消解，文件頭部可移除 `Pending Summary` 區塊（Phase 4 Validate 時統一決定 `Status` 升級）。
5. 結束後回菜單。

### E. 自行補充事項

1. 詢問：「請描述要補充的內容，以及希望進入哪個章節？」
2. 使用者輸入後，將內容寫入指定章節，並在 `Last Updated` 章節或附錄 C Change Log 標示「使用者直接補充」。
3. 不執行 Axure/Figma/API 抽取流程。
4. 結束後回菜單。

### F. 現行程式碼局部同步

1. 詢問：「請提供要同步的檔案或資料夾路徑（可多個）。」
2. **共用 Code Sync 引擎**（見 `code-sync-procedure.md`）的 CS-2 與 CS-3，但 scope 限縮為使用者指定的路徑集合。
3. 同樣輸出 Diff Report 供使用者勾選，確認後寫回 spec。
4. 結束後回菜單。
5. 與獨立 Code Sync mode 的差異：F 為「局部」（指定路徑），獨立模式為「全量」（整份 spec 對齊整套 code）。

### G. 其他（自行輸入）

1. 開放式詢問：「請描述要做的事。」
2. skill 判斷影響範圍：
   - 若可路由到 A–F 任一選項 → 改走該選項流程。
   - 若需多個選項組合 → 依序執行。
   - 若仍無法歸類 → 比照 E「自行補充事項」處理。
3. 結束後回菜單。

### H. 結束

1. **若本次有觸發 A 或 B**（待抓清單非空）→ 先執行 **Phase 1.5 confirm gate**：套用 `operating-procedure.md` Step 9 的邏輯，列出本次 A/B 累積的 URL 摘要（例如「Axure: 3 個 / Figma: 5 個（均加 --bust-cache）」），由使用者確認後才進批次抓取（Step 1.5.1 / 1.5.2 / 1.5.3）；若使用者選 n 或要補，回 A/B 補完再回到 confirm gate。
2. 進入 **Phase 2 Reconcile（局部模式）**：只針對本次被改動的章節做交叉比對。
3. 接 **Phase 3 Compose（局部更新）**：保留未動章節原文，只覆寫被改動章節，並於檔頭更新 `Last Updated`、附錄 C Change Log 追加一筆。
4. 接 **Phase 3.5 Post-Draft Q&A（局部模式）**：依 `post-draft-qa-checklist.md` 的「局部模式」段落，只跑 changed sections 的內部審查。
5. 接 **Phase 4 Validate**：完整跑 Validate 清單（不限縮章節，避免遺漏整體一致性問題）。

## Loop 行為

- 每執行完 A–G 任一動作，回菜單並提示：「還要更新其他內容嗎？」
- 使用者再次出題 → 繼續執行。
- 使用者明確選 `H` 或說「結束 / done / 沒了」→ 進入 H 的 confirm gate + Reconcile 流程。
- **A / B 選項內的 wrapper 呼叫一律延後到 H 的 confirm gate 通過後**：不要在使用者貼第一個 URL 時就抓；多次 loop A 或 B 也只在 H 觸發時批次跑一次（同一 URL 重複貼也只跑一次，wrapper 內建 hash 去重）。

## Quick path：使用者已明確說明要動什麼

若使用者第一句已說清要動哪些（例：「我要更新 API 跟回答待確認事項」），**跳過菜單顯示**，直接依序執行 C → D → H。
這對應 `operating-procedure.md` Phase 1 開頭的「快速跳過規則」段落。

## 範圍標記（給 Phase 2 / 3 / 3.5 用）

選項執行時，內部維護一個 `changed_sections` 集合，記錄本次被觸碰的章節。對應關係：

| 選項 | 預設受影響章節 |
|---|---|
| A | 🔄 核心流程、📱 畫面規格、❓ 待確認事項 |
| B | 📱 畫面規格、🔄 核心流程（頁面清單） |
| C | 🔌 API 規格、附錄 A.1/A.2、📱 畫面規格（資料來源段落） |
| D | 依答覆內容對應的章節 + ❓ 待確認事項 |
| E | 使用者指定章節 |
| F | 依 Code Sync 引擎判定（通常為 📐 業務規則「實作位置」、🛠️ 程式影響範圍、🔌 API 規格） |
| G | 視路由結果而定 |

`changed_sections` 在 Phase 3.5 Post-Draft Q&A 用於限縮審查維度。

## 衝突處理

- 若使用者本次的補充與既有 spec 衝突：**保留既有 + 新增為「待確認」**，列入❓ 待確認事項，不擅自覆蓋。對應 SKILL.md 的 Source-of-truth hierarchy。
- 若 Update menu F 同步出 code 與 spec 衝突：依 Code Sync mode 的 Diff Report 流程，使用者勾選才寫回。
