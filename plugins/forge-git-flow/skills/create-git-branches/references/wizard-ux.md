# 設定精靈與 Settings UX

## 共通畫面規則

- 先顯示白話結論，再緊接完整 branch、SHA、ref、remote、URL、JSON 或 command。
- 不隱藏技術資訊，也不把讀 JSON 當成完成流程的前提。
- 對外說「branch 組合」「branch 類型」「名稱規則」「每次變動的內容」。完整 JSON 前可說明底層鍵名。
- 每次儲存都重新詢問套用範圍，不沿用上一次答案。
- 建議、推導或自然語句修改都必須先預覽，永不自動儲存。
- 有多組 branch 組合時一律全部列出，不得靜默沿用上次的組合；`defaults.profile` 只標示為「上次使用」。

## 首次設定

開場明示：

> 約一分鐘完成。設定儲存後，我會直接接著處理你剛才的 branch 建立需求，不用重新輸入。

### 1. 找既有範例

先執行 `config discover --limit 3`。它只能讀 local branches 與已存在的 remote-tracking refs，不連網、不 fetch。

若有可靠候選，首頁最多顯示 3 組，每組都包含建議白話名稱及所有實際 branch 範例：

```text
[ ] 共同分支
    stg/s182_login_flow
    ut/s182_login_flow
[ ] 功能開發
    stg/s182_login_flow
    ut/s182_login_flow
    jason/feature/s182_login_flow

[4] 顯示更多（最多 5 組）
[5] 貼上自己的實際 branch 範例
```

允許多選並持續加入例子。每輪結尾提供「繼續加入／這些就是全部／取消」。不要因使用者選了第一組就假設其餘情境不存在。

找不到可靠候選時，直接請使用者貼上同一項工作會建立的 branch，一行一條。仍沒有範例時才用逐題白話建立器詢問：

1. 一次通常建立哪些 branch。
2. 用目前需求示範時，每條完整名稱長什麼樣。
3. 哪些片段每次會變。
4. 預設是否 push、是否切換 branch。

不要向使用者顯示 starter、target、profile 或 template 選擇題。

### 2. 推導與追問

比較多個實例，推導固定片段與每次變動片段。只追問無法可靠判斷之處，例如：

- `jason` 永遠固定，還是依負責人改變？
- `s182` 是固定文字，還是每次會變的 Sprint？

為每組提出可修改的白話名稱，實際 branch 範例必須同畫面顯示。使用者調整名稱只改 presentation label，不改 branch。

### 3. 用原需求驗證

從觸發本次流程的原始需求抽取 slug、ticket、Sprint、負責人；只追問仍缺少且規則實際使用的值。寫出候選 JSON 到暫存檔，執行 `config preview`，以原需求展開所有組合。

### 4. 套用範圍與確認

先對 project 與 global 候選各執行一次 `config preview`。在詢問 scope 前，展示目前設定，以及兩種候選的完整 branch 和 JSON；若 project override 使 global 修改在目前專案不生效，必須明說。接著每次儲存都詢問：

```text
[1] 只套用目前專案
[2] 設為其他專案的預設規則
    已有專屬設定的專案仍以自身設定優先。
```

確認畫面固定依序顯示：

1. 白話規則摘要。
2. 每組完整 branch 結果。
3. 哪些值每次會詢問。
4. push／checkout 預設。
5. 套用範圍、繼承關係與 exact 設定檔位置。
6. 完整底層 JSON。

最後只提供「儲存並繼續／返回調整／取消」。儲存後直接回到原始建立需求的 source 畫面。

## 回訪路徑（已設定）

已經有設定的每一次建立需求，都從現況摘要與入口選單開始，不得靜默沿用上次的組合。目的是讓使用者每次都看見自己有哪幾組、可以增刪改。

### 1. 現況摘要與入口選單

執行 `config options --repo <repo>`（不帶 `--slug`），先顯示全部組合的白話名稱與 branch 形態，再顯示名稱規則、套用範圍與 exact 設定檔路徑：

```text
目前的 branch 規則（來源：本專案設定 /Users/you/.local/share/create-git-branches/projects/repo-abc123.json）

  Feature 功能開發（上次使用）
      c/stg/{base}
      c/ut/{base}
      jason/feature/{base}
  Task 功能開發
      c/stg/{base}
      c/ut/{base}
      jason/task/{base}
  不開 owner branch
      c/stg/{base}
      c/ut/{base}

  名稱規則  s{sprint}_{slug}      例：s183_login_flow
  預設      不自動 push、不切換 branch

[1] 直接開始建立
[2] 變更 branch 組合（新增／修改／刪除）
[3] 變更名稱規則
```

`{base}` 代表名稱規則展開後的結果，要在畫面上以一句話說明。使用者一開始就講清楚要改什麼時（「Sprint 改成 183」「新增一組只建立 stg 和 qa」），直接進對應子流程，不必先顯示這個選單。

### 2. 變更 branch 組合

```text
[1] 新增一組
[2] 修改現有的一組
[3] 刪除一組
```

- **新增一組**：問這一組要建立哪些 branch（列出所有已知 branch 類型的白話名稱與形態，允許多選；也允許貼上一條新的完整 branch 範例來推導新類型）→ 問這一組的白話名稱 → 進入下方共通儲存流程。
- **修改一組**：先顯示該組目前的完整 branch，再讓使用者增減 branch 類型或改白話名稱 → 共通儲存流程。
- **刪除一組**：顯示該組完整 branch 與白話名稱，說明刪除後將無法再選用（既有 branch 不受影響）→ 共通儲存流程。

`config set` 是整份 scope 覆寫，因此同一個 scope 內的刪除直接可行。但 project 設定無法刪除 global 已定義的組合（只能覆蓋同名的一組），遇到時要明說並建議改到 global 操作。

### 3. 變更名稱規則

名稱規則全域只有一條，所有組合共用。先用本次需求展示修改前後對照，再進共通儲存流程：

```text
   目前   s{sprint}_{slug}   →  c/stg/s183_login_flow
   修改後 {ticket}_{slug}    →  c/stg/ABC-123_login_flow
```

只有這一次要用特別的名字時，不要改規則 —— 回到建立流程的名稱候選選單選「自訂名稱」即可。

### 4. 共通儲存流程

新增、修改、刪除、變更名稱規則都走同一條路：寫候選 JSON 到暫存檔 → 對 project 與 global 各執行一次 `config preview` → 依「套用範圍與確認」的固定 6 段確認畫面 → 「儲存並繼續／返回調整／取消」。

儲存後直接回到原本的建立需求繼續，不要求重新輸入。從 `settings` 進入時則停在現況摘要，不接續建立。

## Settings

`/create-git-branches settings` 與上面的回訪路徑共用同一份現況摘要與入口選單，差別只在完成後不接續建立。進入時執行 `config options`，需要完整 effective JSON 時再補一次 `config show`，先顯示：所有白話組合、每組實際 branch 範例、套用範圍、global/project 繼承來源、push/checkout 行為、設定檔及 previous 路徑、完整 effective JSON。

優先解析自然語句，例如：

- 「Sprint 改成 183」
- 「功能開發不要建立 ut」
- 「新增一組只建立 stg 和 qa」

語意足夠明確就產生候選設定，不要求使用者先選技術分類或 scope。先用目前示例展示修改前結果，再對 project/global 候選各執行 `config preview`，展示兩種修改後的完整 branch 與 JSON；完成前後比較後才詢問套用範圍。語意不清時顯示：

```text
[1] 一次建立哪些 branch
[2] branch 名稱長相
[3] 每次會變的內容
[4] push／checkout 行為
[5] 套用範圍
[6] 復原上一版或重新設定
```

每次修改都先顯示修改前後的完整實例及 JSON，然後重新詢問套用範圍與「儲存／返回調整／取消」。不得先問 scope 才產生修改後預覽。

復原先執行不帶 confirmation 的 `config restore`，再以目前示例對 current/restored 各執行 `config preview`，展示前後完整 branch 與 JSON；使用者選單確認後才在內部帶 `--confirm RESTORE`。Reset 同理，使用者只確認白話後果，不輸入技術字串。

## 對話驗收情境

執行或人工檢查下列情境：

1. 首次設定多組規則，儲存後接續原建立需求。
2. 無可靠候選，改由使用者貼實際範例。
3. 自然語句修改成功並展示前後。
4. 模糊修改回到六項分類選單。
5. 連續兩次儲存都重新詢問 scope。
6. source、local、push 與 settings 畫面同時具有白話摘要及完整技術資訊。
7. 已有多組設定時再次建立，第一個畫面就看到全部組合、名稱規則與入口選單。
8. 從建立流程新增一組並儲存後，自動回到本次建立需求，不需重新輸入。
9. 選擇組合時全部組合都列出，「上次使用」只是標記，不會自動選取。
10. 刪除一組後再次建立，該組不再出現於選單。
