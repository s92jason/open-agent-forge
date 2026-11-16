# feature-spec-builder 運作機制與設計原理

> 這份文件回答一個問題：**為什麼這個 skill 能把 Axure / Figma 的零碎設計資料，
> 穩定地整理成一份 RD / QA / AI 都能讀的工程規格，甚至畫出流程圖、列出完整業務邏輯？**
>
> 對象：維護者、使用者，以及想評估「能不能信任這個 skill」的人。
> 這不是操作手冊（操作流程見 `SKILL.md` 與 `references/operating-procedure.md`），
> 而是「信心文件」——把背後的機制攤開，讓你知道它不是黑魔法，而是有設計的工程。

---

## 一句話總結

> **這個 skill 的本質，是「確定性抽取」加「AI 語意合成」的混合架構：
> 機械的事（認證、抓取、解析私有格式）交給不會幻覺的 Python 腳本；
> 判斷的事（跨來源比對、衝突裁決、編譯成規格、生成流程圖）交給 AI。
> 兩者之間用一份『正規化 JSON』當橋樑。**

它之所以「好用且可信」，不是某一招神奇，而是四層設計互相加成：
**確定性抽取 + 剛性章節 schema + 誠實的不確定性處理 + 防斷流的完成契約。**

---

## 一、核心心智模型：自然語言程式 + I/O 驅動

先建立一個能貫穿全部的框架。這個 skill 本質上是**兩種程式碼的疊加**：

| 層 | 載體 | 負責的事 | 特性 |
|----|------|---------|------|
| **控制層 / 編譯規則** | Markdown（`SKILL.md` + `references/`） | phase 流程、停點、章節 schema、衝突優先序、pending 標記 | 給 AI 讀的「程式」 |
| **I/O 驅動層** | Python（`scripts/`） | 認證、抓取、解析、抽文字、推狀態、cache | 給機器跑的「驅動」 |

關鍵體悟：**這個 skill 大約一半是「用中文寫的程式」。** Markdown 不是說明文件，
它就是 AI 要逐步執行的有限狀態機（FSM）—— phase、gate、停點都是 control flow，
只是用自然語言表達。而 Python 腳本「不做任何判斷」，只做 LLM 做不到的事
（跟 Axure 做 SHA-512 認證、呼叫 Figma REST API、解析壓縮過的 JS）。
凡是需要「理解語意」的工作，全部留給 AI。

**AI 在這個架構裡同時扮演四個角色：**

- **直譯器（interpreter）**：讀 `SKILL.md`，照 phase 跑，在對的時機呼叫腳本。
- **編譯器（compiler）**：把正規化 JSON 依章節 schema 編譯成 Markdown 規格。
- **裁決者（reconciler）**：跨來源衝突時依 hierarchy 取捨。
- **自審者（auditor）**：Phase 3.5 對草稿做內部審查。

---

## 二、資料流水線總覽

整條 pipeline 分三段，各由最適合的執行者負責：

```
[來源]              [Python 驅動層：確定性抽取]            [AI 層：語意合成]
Axure share link ─┐
Figma URL        ─┼─► extract_with_cache.py (cache gate)
API doc (純文字)  ─┘        │
                            ├─► extract_axure_page.py ─┐
                            └─► extract_figma_page.py ─┼─► 正規化 JSON (IR)
                                                       │   {pages/frames,
                                                       │    text_content,
                                                       │    inferred_state}
                                                       │
                                                       └─► Phase 2 Reconcile
                                                           → Phase 3 Compose
                                                           → Phase 3.5 Q&A
                                                           → Phase 4 Validate
                                                                  │
                                                          FEATURE-SPEC.md
```

**兩次轉化，各司其職：**

1. **私有格式 → AI 友善的事實清單**（Python 做）：把「人類設計工具的私有格式」
   壓成「扁平、乾淨、AI 好讀」的 JSON。
2. **事實清單 → 工程規格**（AI 做）：把碎片重新連線、編譯成結構化文件。

---

## 三、第一層：確定性抽取（為什麼這層要存在）

extractor 把兩種天差地別的來源，收斂成**同一種形狀**的 JSON。
這是編譯器領域講的 **Intermediate Representation（IR，中間表示）**。

### 3.1 Figma：有官方 API，所以單純

`extract_figma_page.py` 走 Figma REST API：

- `fetch_file_structure` 打 `/v1/files/{key}?depth=3`，帶 `X-Figma-Token`。
- `extract_frames` 遞迴穿透 `SECTION` / `GROUP` 容器，撈出所有 `FRAME` / `COMPONENT`，記下寬高。
- `collect_text` 遞迴蒐集所有 `TEXT` node 的 `characters`。
- **`visible: false` 的圖層會被過濾掉**（`extract_frames` 與 `collect_text` 都先檢查）——
  這是「降噪」：設計稿常有廢棄草稿、隱藏圖層，先在抽取層濾掉，AI 就不會把垃圾寫進 spec。

### 3.2 Axure：沒有 API，所以這支腳本在「逆向工程」

`extract_axure_page.py` 是整個 skill 最硬核的程式碼。Axure Cloud 沒有公開 API，
所以它在還原 Axure 的網頁協定：

1. **認證**（`authenticate`）：把 access code 用 `SHA-512` hash，POST 到
   `/prototype/dologin/<ID>`，從回應撈出 auth cookie。
2. **抓 sitemap**（`fetch_document_js`）：取得 `data/document.js`，這是一個**被極致壓縮的 JS 檔**。

`document.js` 長這樣（Axure 為了減少體積，把所有字串抽成單字母變數指標）：

```js
var v="id",w="g3k2p1",x="pageName",y="登入頁",z="type",A="Axure:Page",B="url",C="login.html",...
var _creator=function(){return _(q,_(u,[_(v,w,x,y,z,A,B,C), ...]))};
```

`parse_sitemap` → `_parse_compressed_format` 用三步把它還原：

- **Step 1 建 var_map**（`assign_pattern` regex）：把每個 `名字="值"` 掃進字典，
  並處理 `0xFF` / 數字 / `true/false/null` 等型別。
- **Step 2 反查鍵變數**：腳本不知道 `x` 代表什麼，但知道頁面物件一定有 `pageName` 這個鍵，
  所以反過來找「值等於 `"pageName"` 的那個變數」，鎖定 `pageName_var` / `url_var` / `id_var` 等。
- **Step 3 還原頁面**（`_find_all_page_calls` + `_resolve_entry`）：掃描所有 `_(...)` 呼叫，
  用括號深度計數找出範圍，把交替的「鍵,值」對還原成頁面物件。

**一個極易寫錯、作者特地註解的陷阱**：`_find_all_page_calls` 前進時用 `i += 1`（逐字元）
而不是 `i += j`（跳到配對括號）。因為 Axure 把頁面 `_()` 巢狀塞在外層 `_()` 裡
（`_(config, _(rootNodes, [_(id,...), ...]))`），若跳到配對括號結尾，會略過整個外層、
**漏掉所有巢狀頁面**。逐字元掃雖笨，但對巢狀安全；`document.js` 通常只有幾十 KB，
逐字元掃也就毫秒級，正確性 >> 效能。

**三層 fallback（韌性設計）**：`parse_sitemap` 其實是三段防線——
壓縮格式解析 → 未壓縮 JSON 解析 → regex 硬撈。即使全失敗，
`main()` 還會輸出 `degraded: true` + 截斷的 `raw_document_js`，讓人手動分析而非崩潰。
（對應 `operating-procedure.md` Step 1.5.3：`degraded` 或 `page_count==0` 視同失敗、
列入錯誤匯報。）

### 3.3 正規化 IR：兩種來源收斂成同一形狀

無論 Axure 還是 Figma，最後都吐出同一個結構：

```json
{ "pages" / "frames": [
    { "name": "...", "text_content": ["...", "..."],
      "inferred_state": "login" / "loading" / "error" / "success" / "default" }
]}
```

**為什麼要這道正規化？** 因為 AI 處理乾淨 JSON 的成功率，遠高於處理一坨壓縮 JS
或巨大的 Figma node tree。把髒活擋在 AI 之前，等於幫 AI「降低認知負荷」，
這直接提升輸出品質與穩定度。而且兩種來源形狀一致，Phase 2 可以用同一套邏輯交叉比對，
不用為每種來源寫特例。

### 3.4 狀態初判是「故意粗糙」的

`inferred_state` 只是關鍵字比對（`infer_state` + `_STATE_KEYWORDS`，中英都吃）。
這是 **weak heuristic**：extractor 只給「初判標籤」，真正細緻的狀態判斷（觸發條件、
畫面行為）留給 AI 結合 `text_content` 細寫。兩個 extractor 的關鍵字表是「故意重複」的
（程式碼有註解提醒同步），Axure 版多了 `login` / `popup` 兩種狀態，因為原型常含登入頁與彈窗。

---

## 四、核心疑問：為什麼「攤平的流水帳」AI 能還原成精確流程？

這是最反直覺、也最關鍵的一點。extractor 給 AI 的，看起來只是「把網頁上的字攤平塞進 List」，
人類看不出流程關係。但**丟失的是『箭頭的畫法』，沒丟的是『箭頭上的標籤』**——而對 LLM 來說，
標籤就足夠把圖重新接回來。五個機制：

### 機制一：箭頭丟了，但箭頭上的標籤還在

很多 Axure「流程圖頁」（`type: Wireframe`）本身就是設計師手繪的流程圖：方框、箭頭、
條件標註。extractor 把它「壓平」成字串清單，但**節點與標籤都完整保留**。
有時連箭頭都原封不動：`"手機號碼已註冊過小樹會員 →登入流程"`、
`"若 AuthFlag != Y 則 顯示同意資料共享"`——這根本是 if-then 規則的白話文。

### 機制二：決策節點、分支條件、結果，本身就是文字

流程圖的三種核心元件全在清單裡：

- **決策菱形**：`"是否取得網址"`、`"是否綁定銀行成功"`、`"寫入是否成功"`
- **分支條件（edge label）**：`"OrcaMemberStatus=0/1/2/3"`、`"RETURNCODE=0000"`、`"！= 0000"`
- **結果節點**：`"綁定成功"` / `"綁定失敗"`、`"註冊+綁定銀行成功"` / `"...失敗"`

一個「是否綁定銀行成功」配上「綁定成功 / 綁定失敗」，對 LLM 就是一個完整的決策分支。
散落的表格列（錯誤碼 `E101 → 訊息 → CTA → 情境`）因為 extractor 大致依 DOM 順序抽取，
**同一列的儲存格傾向相鄰出現**，AI 能把它「重新裝訂」回表格。

### 機制三：Figma 的 frame「名字」就是一套結構化 ontology

即使 `text_content` 全空，frame 名字本身就帶 schema：
`<畫面編號>_<功能模組>_<畫面>_<狀態變體>`，例如
`8E-2 個人權益_授權小樹會員開通_介紹頁_error`。光從名字，AI 就能解析出畫面身分、
狀態變體（`_error` / `_loading` / `_success` / `_九位數`）、happy path 順序，
甚至辨識「375px = iOS、360px = Android」同畫面雙份並合併去重。

### 機制四：跨來源三角驗證（準確度的真正放大器）

單看 Axure 或 Figma 都殘缺，疊起來互相補完、互相確認：Axure 富含「邏輯」
（狀態機、條件、API、錯誤碼）但少畫面長相；Figma 富含「畫面清單與狀態」但 text 多半空。
一個錯誤碼 `EO04`，在 Axure 是一列表格、在 Figma 是 `小樹會員已被使用 popup` 這個 frame——
**兩源都指向同一件事，信心拉滿**。能三角驗證的拉滿信心，單源又模糊的就標 `[待確認]`。

### 機制五：LLM 自帶「流程骨架」的先驗知識

LLM 在訓練時看過成千上萬個「會員註冊 + 綁定 + 同意條款 gate」這類流程，
腦中有現成骨架。它把資料裡的具體 fragment（`OrcaMemberStatus=N`、各電文代碼、
回拋機制）卡進骨架的對應槽位。**所以「能畫出流程圖」= 資料提供節點與標籤（機制一二）
+ LLM 先驗提供骨架形狀（機制五），兩者相乘才有那張準確的圖。**

### 為什麼人拼不起來、AI 可以

不是資訊量問題，是「同時持有」的能力。一頁流程圖可能有上百條 fragment，
人類線性閱讀撐不住這麼多交叉引用；LLM 的 attention 機制本質上就是
「把每條 fragment 同時和所有其他 fragment 配對、算關聯、重新連線」。
**攤平清單對人是詛咒，對注意力機制剛好是最擅長的輸入形式。**

---

## 五、第二層：AI 編譯（為什麼產出「精細」）

精細度不是來自 AI 特別聰明，而是來自 **schema 約束**。

### 5.1 剛性章節 schema（`references/chapter-rules.md`）

每一章都被定義成「有型別的表單」，AI 是在填欄位，不是自由寫作：

- **🔌 API 規格**強制分「前端使用的回傳欄位」vs「前端不使用的欄位（含原因）」——
  逼 AI 對每個欄位做二元裁決。
- **📐 業務規則**每張表強制有「實作位置」欄（初始 `TBD`，功能完成後回填檔案行號）。
- **✅ 驗收條件**強制拆成「正常 / 邊界 / 失敗」三張 Given-When-Then 表——逼 AI 窮舉 edge case。

**精細 ≠ 冗長：** 約束愈強，AI 愈不會寫「優化體驗」這種空話（Tone 章節明文禁止）。
精細度是 schema 逼出來的，不是放飛出來的。

### 5.2 Single Source of Truth per Dimension

每條規則只在一個章節完整定義，其他章節只引用。這在「防止 AI 自我矛盾」——
LLM 在長文件裡最容易犯的錯，就是同一欄位在兩章各寫一遍、還對不上。
把每個事實限制在唯一住所，從根本上消除 drift。`chapter-rules.md` 還給了量化違規判定：
「同一欄位邏輯在兩章以上各展開超過一行 = 違反」。

### 5.3 流程圖：現成節點 → Mermaid 文字 DSL

流程圖的節點來自 Axure sitemap 樹 + `text_content`，AI 只做「把圖結構翻譯成 Mermaid」——
這是 LLM 擅長的事，因為節點集合已由確定性程式給定。`chapter-rules.md` 還規定
**「頁面清單表格必須放在 Mermaid 之前」**，因為 Mermaid 在某些環境（GitHub mobile、
某些 IDE）渲染不出來——這是 graceful degradation，同一份資訊用兩種形式表達。

### 5.4 三模式形成雙向收斂閉環

- **Create mode**：設計稿 → IR → spec，刻意在📐業務規則留「實作位置: TBD」。
- **Update mode**（`references/update-mode-menu.md`）：菜單式，靠 `changed_sections`
  只覆寫被碰過的章節，不暴力整寫；A/B 重列 URL 必加 `--bust-cache`（明示要 refetch）。
- **Code Sync mode**（`references/code-sync-procedure.md`）：**方向反轉**——掃 Kotlin/Compose
  程式碼反向校準 spec，回填 TBD、揪出 code 與 spec 的不一致（CS-1~CS-4，read-only Diff Report，
  使用者勾選才寫回）。

閉環設計：Create 時留 TBD，功能寫完用 Code Sync 把 TBD 回填成真實檔案行號，
spec 與 code 因此雙向收斂、不 drift。Update menu F = 局部版 Code Sync，共用同一 CS-2/CS-3 引擎。

---

## 六、信任機制（為什麼可信，不亂編）

這層是「能不能信任它」的關鍵。skill 用四個機制確保它**重建而不偽造**：

1. **Source-of-truth hierarchy**：衝突時依固定優先序取捨，不隨機——
   互動流程信 `Axure > Figma`、視覺狀態信 `Figma > Axure`、資料契約信 `API > code > 設計稿`。
   最高優先永遠是「使用者確認的需求」與「API contract」。

2. **三層 pending 標記**：待補資訊同時出現在①檔頭 `Pending Summary`、②章節內 `[Pending]`、
   ③文末 `❓ 待確認事項`。**不確定的東西被顯式標記，而不是被幻覺成已定稿。**

3. **Phase 3.5 強制 Q&A gate**：草稿含任何 pending / conflict / 未確認推論，
   **必須**輸出問題清單並停下等使用者。「把 pending 寫進 spec ≠ 通過」。
   進 Phase 4 前必須輸出 gate disposition（`PASS_NO_QUESTIONS` / `PASS_USER_CONFIRMED` /
   `PASS_USER_CONTINUE`）。

4. **完成契約（防斷流）**：只有 Phase 4 通過才算完成；產出 `FEATURE-SPEC.md` 只是草稿。
   全程只有三個合法停點（Phase 1 提問、Phase 1.5 補憑證、Phase 3.5 問題清單），
   其餘連續執行。這是在對抗一個真實的 LLM failure mode——「吐完大 artifact 後傾向收手」。

5. **機密不落地**：Figma token / Axure access code 存在系統 Keychain
   （`scripts/keychain_helper.py`），**絕不寫進 repo、`FEATURE-SPEC.md`、change log 或一般輸出**。

6. **Cache 強指紋**（`scripts/extract_with_cache.py`）：cache 命中要通過 7 道檢查
   （source_type / url / page / **extractor 版本** / TTL 7 天 / 輸出檔 sha256 完整性），
   任一不符就重抓。「明示意圖 = bust cache」：Update menu 重列 URL 即清 cache 重抓。

---

## 七、已知限制與邊界（誠實揭露）

- **它是「重建」不是「解析」**：節點之間的『順序 / 方向』若來源沒有顯式箭頭，AI 會用流程原型
  推論，**可能把分支接反**。這正是 Phase 3.5 Q&A 與 `[Conflict]` 標記存在的原因——
  把不確定攤開讓人覆核。
- **Code Sync 初版只支援 Kotlin / Compose**：其他語言（JS/TS、Swift）會標「[語言未支援]」。
- **Axure 限 `axshare.com` share link**：非 axshare 格式的 Axure Cloud link 需 fallback
  （PDF / 截圖 / 文字）。
- **不承擔 PM/PRD 責任**：輸出給 RD/QA/AI，不做產品敘事。
- **設計來源不足時不假裝完成**：至少需一個設計來源（Axure 或 Figma），否則只出標記為
  `Draft` 的骨架。

---

## 八、結語：好用的本質

這個 skill 好用，不是因為它「很聰明」，而是因為它**把一件 AI 本來就擅長的事
（從碎片重建關聯），框成穩定、可覆核、不亂編的工程流程**：

- 用 **IR 正規化**讓 AI 只面對乾淨資料；
- 用 **章節 schema** 把「寫規格」變成「填型別表單」，逼出精細度、消除自我矛盾；
- 用 **hierarchy + 三層 pending + Q&A gate** 確保它誠實標記不確定，而非偽造；
- 用 **完成契約**確保它真的跑完；
- 用 **三模式閉環**讓 spec 成為跟 code 雙向收斂的活文件。

確定性的歸確定性，判斷的歸判斷，中間用一份乾淨的 JSON 接起來——這就是它能成功的全部祕密。
