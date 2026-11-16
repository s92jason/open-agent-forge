# Post-Draft Q&A Checklist（Phase 3.5）

目的：主動發現草稿中的缺漏與不明確，透過問答提高精準度。**無論草稿品質如何，此步驟為強制執行。**

## Q&A Gate（硬規則 — 進 Phase 4 的唯一通道）

1. **觸發條件**：只要本次草稿（Update mode 局部模式 = `changed_sections` 範圍）含下列任一項，就**必須**執行 Step 2～4 輸出問題清單並停下等待使用者回覆：
   - `[Pending]`、`[Conflict]`、`[Needs confirmation]`、`[Source not provided]`、`Pending API confirmation`
   - 非空的 `Pending Summary` 或 `❓ 待確認事項`
   - 任何模型推論且未經使用者確認的內容
2. **把 pending 寫進 spec ≠ Phase 3.5 通過**。pending 標記的職責是「記錄未知」，Phase 3.5 的職責是「把未知拿去問」，兩者缺一不可。「pending 都已標注並有對應 ❓ 條目」只代表文件格式合規，不代表可以跳過提問。
3. **Gate disposition（必輸出、對使用者可見）**：進入 Phase 4 前，必須輸出一行 disposition，且只能是以下三值之一：
   - `Phase 3.5 gate: PASS_NO_QUESTIONS` — Step 1 全過 **且** Step 1.5 Pending Scan 命中 0
   - `Phase 3.5 gate: PASS_USER_CONFIRMED` — 已提問，使用者逐項回覆，spec 已依回覆更新
   - `Phase 3.5 gate: PASS_USER_CONTINUE` — 已提問，使用者明說「繼續」，pending 保留並標記
   未輸出 disposition 即進 Phase 4 = 違反本 skill。`PASS_NO_QUESTIONS` 只在 scan 命中 0 時合法；scan > 0 卻想用它，回到第 1 條。

## 模式變體

- **Create mode**：對整份 spec 跑下方所有審查維度。
- **Update mode（局部模式）**：**只針對本次菜單觸碰的章節**（`changed_sections` 集合）跑相關審查維度。未被觸碰的章節保留原狀，不重新審查——這是避免重複追問舊 pending 的關鍵。對應規則：
  - 若本次只動 🔌 API 規格（菜單 C），只跑「🔌 API 規格…」「[Pending] 與❓ 待確認事項對應」「Single Source of Truth（限該欄位）」三項。
  - 若本次動 📱 畫面規格（菜單 A/B），追加「📱 畫面規格的 state table…」與「🔄 核心流程…」。
  - 若本次動 📐 業務規則（菜單 D/E/F），追加「📐 業務規則…實作位置欄位」。
  - 全 yes 仍可早退至 Phase 4，但**早退仍須通過 Step 1.5 Pending Scan（限 `changed_sections` 範圍，命中 0）並輸出 gate disposition**；早退時於對話末尾告知使用者「本次局部 Q&A 通過，未變更章節維持原狀」。
- **Code Sync mode**：**完全跳過 Phase 3.5**。Code Sync 的本質是事實核對，再做 Q&A 會冗餘；改由 CS-3 Diff Report 取代品質檢查。

## Step 0：宣告進入 Phase 3.5（對使用者可見，必輸出）

進入內部審查前，**必須先輸出一行可見訊息**作為續跑錨點，例如：

```
草稿已產出，正在執行 Phase 3.5 內部審查（檢查流程涵蓋度、state table、欄位來源、Single Source of Truth…）。
```

這一行的作用是把「不可見的內部審查」轉成有明確動作的步驟 —— 一個完全不輸出的步驟等於沒有 enforcement，最容易在草稿產出後被 agent 當成「任務已結束」而跳過。輸出後**不要等待使用者回應**，直接執行 Step 1。

## Step 1：內部審查（不輸出給使用者）

針對以下維度逐項判斷（yes / no / unclear）。Update mode 局部模式下，只跑與 `changed_sections` 相關的維度：

- 🔄 核心流程是否涵蓋 Axure 上的所有分支（含替代流程、失敗處理）？（無 Axure 來源時，以 Figma prototype / 使用者描述為準；確實無從判斷者記 N/A，不算 unclear）
- 🔄 核心流程是否有頁面清單表格（在 Mermaid 圖之前）？
- 📐 業務規則的每張規則表是否都有「實作位置」欄位？
- 📱 畫面規格的 state table 是否覆蓋 loading / success / empty / error？
- 🔌 API 規格是否明確區分「前端使用」與「前端不使用」的欄位？
- 模型自行推論的內容是否**全部**已標注來源？
- 每個 [Pending] 是否**都有**對應的❓待確認事項條目？
- **Single Source of Truth**：同一欄位的行為邏輯是否只在一個章節完整定義？

所有維度均為 yes **只是必要條件**，不構成早退理由；仍須通過 Step 1.5 Pending Scan（命中 0）才能以 `PASS_NO_QUESTIONS` 進 Phase 4。任一維度 no/unclear **或** scan 命中 > 0 → 進 Step 2。

## Step 1.5：Pending Scan（機械式掃描，強制執行）

對剛寫出的 `FEATURE-SPEC.md` 執行標記掃描（有 shell 時優先用指令，產出可驗證證據）：

```bash
grep -n -E '\[Pending\]|\[Conflict\]|\[Needs confirmation\]|\[Source not provided\]|Pending API confirmation' <path>/FEATURE-SPEC.md
```

- 無法執行 shell 的 harness：逐章節目視掃描，**逐行列出**每個命中（不可只回答「有/沒有」）。
- Update mode 局部模式：只統計 `changed_sections` 內的命中；未觸碰章節的舊 pending 不算（避免重複追問已存在的舊 pending）。
  做法：先 `grep -n '^## ' FEATURE-SPEC.md` 取得各章節起始行，將 scan 命中行號對映到
  所屬章節；只計入屬於 changed_sections 的命中，並在輸出證據時標注「章節（行號）」。
- 另外檢查 `Pending Summary` 與 `❓ 待確認事項` 是否非空（同範圍規則）。
- **命中數 > 0 → 一律進 Step 2，禁止早退**；命中數 = 0 且 Step 1 全 yes → 輸出 `Phase 3.5 gate: PASS_NO_QUESTIONS` 後進 Phase 4。

## Step 2：整理問題清單

把所有 `no` 或 `unclear` 的項目轉為提問，分為：

- **阻斷類**：缺少會讓 spec 有誤導性或嚴重缺漏的資訊。`[Conflict]` 一律屬阻斷類；提問時須說明目前草稿採用的 hierarchy 預設（例：互動流程已採 Axure 版本），讓使用者可以一句話改判
- **澄清類**：有助提升精準度，但 spec 仍可繼續推進

## Step 3：輸出問題（對使用者可見）

固定格式：

```
第一版草稿已完成。在最終化之前，我有以下問題確認：

**[需確認 — 可能影響 spec 正確性]**
1. ...

**[澄清 — 有助提升精準度]**
2. ...

請逐項確認，或直接說「繼續」使用目前推論並標記為 pending。
```

## Step 4：處理回應

- 已確認者：依回應更新 spec，移除對應 pending 標記 → disposition 為 `PASS_USER_CONFIRMED`
- 說「繼續」：保留推論，將阻斷類問題加入❓待確認事項標記 [Pending] → disposition 為 `PASS_USER_CONTINUE`
- 部分確認：已確認者更新，未確認者比照「繼續」加入❓待確認事項 → disposition 為 `PASS_USER_CONTINUE`

## Step 5：判斷第二輪與輸出 disposition

若使用者回應帶出新衝突或缺漏，執行第二輪 Q&A；否則進 Phase 4。第二輪以一輪為限。

進 Phase 4 前，依 Step 4 的結果輸出對應的 gate disposition 一行（見檔首「Q&A Gate」第 3 條）。
