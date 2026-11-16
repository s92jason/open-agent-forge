# analysis.json 格式

`analysis.json` 是這個 skill 唯一的審查輸出。頁面上的導讀、分組、行內意見都從它產生，
`ingest` 會逐項檢查它，所以欄位名稱與型別要照這份文件。

它包含三種內容：

- **導讀**（`guide`、每組的 `focus`、檔案的 `note`／`skim`、`annotations`）：幫 reviewer 讀懂變更，寫法見 `reading-guide.md`
- **分組**（`groups`）：閱讀順序，寫法見 `grouping-guide.md`
- **審查結論**（`summary`、`score`、`findings`、`notes`）

## 範例

```json
{
  "summary": "主要風險是快取沒有失效時機，領券後會看到舊資料；ViewModel 的錯誤狀態也沒有被畫面處理。建議先補快取失效再合併。",
  "guide": {
    "background": "優惠券列表每次進入畫面都重新打 API，列表頁與結帳頁各打一次，慢而且浪費流量。",
    "approach": "在 `CouponRepository` 加一層以 userId 為 key 的記憶體快取，畫面只透過 Repository 取資料。快取放在 Repository，所以列表頁與結帳頁共用同一份。",
    "flow": [
      { "text": "使用者打開優惠券頁，`CouponViewModel.load()` 被呼叫", "group": "g3" },
      { "text": "`load()` 呼叫 `CouponRepository.getCoupons(userId)`：先查快取，沒有才打 `CouponApi`", "group": "g2" },
      { "text": "結果轉成 `CouponUiState.Loaded`，由 `CouponScreen` 畫出列表", "group": "g3" }
    ]
  },
  "score": {
    "total": 78,
    "meaning": "需修正後合併：有一個會讓使用者看到錯誤資料的問題。",
    "items": [
      { "category": "Correctness & Reliability", "score": 20, "max": 30, "notes": "快取沒有失效（`CouponRepository.kt:44`）。" },
      { "category": "Architecture & Design", "score": 18, "max": 20, "notes": "分層清楚。" },
      { "category": "Readability & Maintainability", "score": 13, "max": 15, "notes": "" },
      { "category": "Testability & Tests", "score": 10, "max": 15, "notes": "快取路徑沒有測試。" },
      { "category": "Performance & Resource", "score": 9, "max": 10, "notes": "" },
      { "category": "Security / Privacy / Compliance", "score": 8, "max": 10, "notes": "" }
    ]
  },
  "groups": [
    {
      "id": "g1",
      "title": "優惠券資料模型",
      "summary": "新增 `Coupon` 與到期狀態。先看這組，後面每一組都會用到這些欄位。",
      "focus": ["`expiresAt` 是 nullable：沒有到期日的券在後面各組有沒有被處理？"],
      "files": ["domain/model/Coupon.kt", "domain/model/CouponStatus.kt"],
      "relations": []
    },
    {
      "id": "g2",
      "title": "查詢與快取",
      "summary": "API 新增查詢端點，Repository 加上以 userId 為 key 的記憶體快取。",
      "focus": ["快取在領券或券到期之後有沒有被清掉？（見 f1）", "兩個畫面同時查詢時會不會打兩次 API？"],
      "files": [
        { "path": "data/api/CouponApi.kt", "note": "新增 `fetchCoupons()` 端點的宣告" },
        { "path": "data/CouponRepository.kt", "note": "這組的核心：查詢先走快取" },
        "data/CouponRepositoryTest.kt",
        { "path": "di/DataModule.kt", "note": "只是把新的建構子參數接上", "skim": true }
      ],
      "relations": [
        { "group": "g1", "note": "回傳 `Coupon`" }
      ]
    },
    {
      "id": "g3",
      "title": "列表畫面",
      "summary": "ViewModel 透過 Repository 取資料並轉成畫面狀態，`CouponScreen` 依狀態畫出列表。",
      "focus": ["載入失敗時，畫面會顯示什麼？（見 f2）"],
      "files": ["ui/CouponViewModel.kt", "ui/CouponScreen.kt"],
      "relations": [
        { "group": "g2", "note": "`load()` 呼叫 `getCoupons()`" }
      ]
    }
  ],
  "annotations": [
    {
      "path": "data/CouponRepository.kt",
      "line": 42,
      "end_line": 44,
      "text": "這次變更的核心：先查快取，沒有才打 API，並把結果以 userId 為 key 寫回快取。"
    }
  ],
  "findings": [
    {
      "id": "f1",
      "severity": "P1",
      "path": "data/CouponRepository.kt",
      "line": 44,
      "side": "new",
      "title": "快取沒有失效時機",
      "body": "`cache[userId]` 寫入後不會清除，使用者領券或券到期後，列表仍是舊的。",
      "suggestion": "領券成功後清掉該使用者的快取，或加上 TTL。"
    },
    {
      "id": "f2",
      "severity": "P2",
      "path": "ui/CouponScreen.kt",
      "title": "沒有處理錯誤狀態",
      "body": "`CouponUiState.Error` 在畫面上沒有對應的呈現，失敗時會停在空白。"
    }
  ],
  "notes": {
    "business": ["券到期當下，列表與結帳頁看到的可用券可能不一致。"],
    "testing": ["補一個「領券後重新查詢」的測試，確認拿到的是新資料。"],
    "assumptions": ["沒有看到後端的快取策略，以上假設後端每次都回最新資料。"]
  }
}
```

## 欄位

### 最外層
| 欄位 | 必填 | 說明 |
|---|---|---|
| `summary` | 是 | 2–5 句的**審查結論**：整體風險、最重要的 1–3 個建議。提到意見時寫 id（「最需要處理的是 f1」），不要重述內容；這個 PR 在做什麼寫在 `guide`，這裡不重複。已合併或已關閉的 PR，第一句註明這是事後 review |
| `guide` | 建議 | 整個 PR 的導讀；沒有 `guide.approach` 時 `ingest` 會記一筆警告 |
| `score` | 是 | 依 `scoring-rubric.md` 評分 |
| `groups` | 是 | 至少一組；**陣列順序就是建議的閱讀順序** |
| `annotations` | 否 | 行內的導讀註解；沒有值得講的就給空陣列 |
| `findings` | 否 | 沒有意見時給空陣列 |
| `notes` | 否 | `business`、`testing`、`assumptions` 三個字串陣列 |

### guide
| 欄位 | 說明 |
|---|---|
| `background` | 1–3 句、約 100 字以內：改之前的狀況、為什麼要改 |
| `approach` | 2–4 句、約 150 字以內：這個 PR 的做法與關鍵的設計決定 |
| `flow[]` | 3–7 步的主線。每一步是物件 `{ "text": "…", "group": "<分組 id>" }`，其中 `group` 可以省略；一步也可以只寫成一個字串（等同沒有 `group`）。沒有明顯的執行流程就省略整個 `flow` |

### score
- `total`：0–100 的數字
- `meaning`：一句話說明這個分數代表什麼（可合併／需修正後合併／阻擋合併）
- `items[]`：`category`、`score`、`max`、`notes`。用 `scoring-rubric.md` 的六個項目（名稱照範例），`max` 加總為 100
- `total` 必須等於 `items` 的 `score` 加總
- 評分項目不適用於這個 PR（例如純文件變更的效能）時給滿分，並在 `notes` 註明不適用

### groups[]
| 欄位 | 必填 | 說明 |
|---|---|---|
| `id` | 否 | 省略時自動編成 `g1`、`g2`…；`relations` 與 `guide.flow` 要引用時才需要自己給 |
| `title` | 是 | 這組在做的事，用這次變更的領域語言 |
| `summary` | 否 | 1–2 句：這組做了什麼，以及它為什麼排在這個位置（「零星調整」那一組可以逐項列出） |
| `focus` | 建議 | 0–3 條字串：看這組時人應該親自確認的事，寫成可以對著 diff 回答的問題；沒有就省略，不要湊 |
| `files` | 是 | 這組的檔案，**順序就是組內的閱讀順序**。每一項是路徑字串，或 `{ "path", "note", "skim" }`；路徑要與 `pr.md` 檔案清單裡的完全一致 |
| `relations[]` | 否 | `group` 是另一組的 `id`，`note` 說明兩組怎麼接起來。每個接點只寫一次，寫在後面（用到別人）的那一組；同一對分組之間有多個接點時可以寫多則 |

`files` 寫成物件時：`note` 是一句話的檔案說明；`skim: true` 代表量大但可以快速掃過（頁面會預設收合），含有邏輯變更、或上面有意見或註解的檔案不要標。

每個變更檔案（包含沒有納入審查的二進位檔與產物）要剛好出現在一組。
漏掉的會被自動放進「未分組」並記一筆警告；改名的檔案用**新路徑**。

### annotations[]
| 欄位 | 必填 | 說明 |
|---|---|---|
| `path` | 是 | 註解所在的檔案 |
| `line` | 建議 | 行號；省略時註解會放在檔案開頭 |
| `end_line` | 否 | 註解涵蓋多行時的最後一行，與 `line` 用同一側的行號 |
| `side` | 否 | `new`（預設）或 `old` |
| `text` | 是 | 1–2 句的說明。這是中性的導讀，不是意見；有問題請寫成 finding |

### findings[]
| 欄位 | 必填 | 說明 |
|---|---|---|
| `id` | 否 | 省略時自動編成 `f1`、`f2`…。要在 `summary` 或 `focus` 引用（「見 f1」）時自己給。第 2 輪以後，仍然存在的意見要沿用上一輪的 id |
| `severity` | 是 | `P0`（不修不該合併）、`P1`（應該修）、`P2`（可以更好）。以這裡的定義為準；`review-checklist.md` 的 P0／P1／P2 標題是檢查的優先順序，不是意見的等級 |
| `path` | 否 | 意見所在的檔案；省略代表針對整個 PR 的意見 |
| `line` | 否 | 行號；省略代表針對整個檔案的意見 |
| `end_line` | 否 | 意見涵蓋多行時的最後一行，與 `line` 用同一側的行號；範圍內可以同時有 `+` 行與上下文行 |
| `side` | 否 | `new`（預設）或 `old`。意見落在被刪除的行時用 `old` 並填舊行號 |
| `title` | 是\* | 一句話講完問題 |
| `body` | 是\* | 為什麼是問題、在什麼情況下會出事 |
| `suggestion` | 否 | 具體怎麼改 |

\* `title` 與 `body` 至少要有一個。

### notes
| 欄位 | 寫什麼 |
|---|---|
| `business` | 使用者或呼叫端看得到的行為有什麼改變，以及產品面的風險（不是程式碼的問題，而是「上線後會發生什麼事」） |
| `testing` | 建議補的測試 |
| `assumptions` | 審查時做的假設，以及在這個 repo 裡無法確認的事（外部系統的行為、作者在 PR 描述裡的主張、沒有審查到的範圍） |

文字欄位一律用繁體中文。可以用反引號標示程式碼（`` `getCoupons()` ``）與三個反引號的程式碼區塊，換行會保留；其餘 Markdown 語法不會被解讀。

## 行號怎麼填
`findings` 與 `annotations` 的行號規則相同。chunk 裡每一行的格式是「舊<行號> 新<行號> 符號 內容」：

```text
    舊41    新41   suspend fun getCoupons(userId: String): List<Coupon> {
    舊42         -     return api.fetchCoupons(userId)
            新42 +     val cached = cache[userId]
            新43 +     if (cached != null) return cached
            新44 +     return api.fetchCoupons(userId).also { cache[userId] = it }
    舊43    新45   }
```

- 落在 `+` 行或上下文行 → `line` 填「新」後面的數字
- 落在 `-` 行 → `line` 填「舊」後面的數字，並加上 `"side": "old"`
- 用 Read 讀 chunk 時，每行最左邊還有一個 Read 自己加的行號，那不是 diff 的行號
- 只能填 chunk 裡出現過的行號。問題在 diff 以外的地方（例如沒被修改的呼叫端）時，把意見掛在最相關的那一行變更上，並在 `body` 說明實際位置

## ingest 會做的事
| 情況 | 結果 |
|---|---|
| 缺少 `summary` 或 `score`、`groups` 為空、`severity` 不是 P0／P1／P2、`score.total` 不是 0–100 或不等於 `items` 的加總 | **error**，不存檔 |
| 分組列了不在變更裡的檔案 | 移除，記警告 |
| 同一個檔案出現在兩組 | 保留第一次出現的位置，記警告 |
| 有檔案沒被分到任何組 | 自動進「未分組」，記警告 |
| 意見的 `path` 不在變更裡 | 改列為整體意見，記警告 |
| 意見的 `line` 不在 diff 內 | 改列為檔案層級的意見，記警告 |
| 沒有 `guide.approach` | 照樣存檔，記警告（頁面會少了導讀） |
| `guide.flow` 的 `group` 不存在 | 拿掉那一步的連結，記警告 |
| 註解的 `path` 不在變更裡 | 略過那一則，記警告 |
| 註解的 `line` 不在 diff 內 | 改放在檔案開頭，記警告 |
