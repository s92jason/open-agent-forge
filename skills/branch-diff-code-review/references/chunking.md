# Chunking strategy（自動分段策略）

## 目標
在 token 過大時，把改動切成「人類也覺得合理」的審查單位，避免：
- 把完全不相關的功能混在同一段
- 把同一功能拆得支離破碎
- 只按檔案數平均切（最常見但最爛）

## 分組優先序（由高到低）
1. **Gradle module 辨識**
   - 以路徑第一層 module（例如 `app/`, `feature/xxx/`, `core/`）分組
   - 若 repo 是多 module，module 是第一級 chunk 邊界

2. **Feature / Domain 命名**
   - 路徑含 `feature`, `domain`, `usecase`, `presentation`, `data` 等，嘗試聚合同一 feature
   - 例如：
     - `feature/payment/*` + `core/payment/*` → 可視為同一功能群

3. **package / namespace**
   - Kotlin/Java：讀檔頭的 `package ...`，以前兩段（e.g. `com.xxx.payment`）聚類
   - Compose/Android 常見：同 package 的 UI + VM + UseCase 優先放一起

4. **檔案類型協同**
   - 同一功能中的 `View/Compose`, `ViewModel`, `Repository`, `Api`, `Mapper`, `Model` 優先同 chunk
   - 若 token 仍爆，才拆成「UI chunk」與「Data/Domain chunk」

5. **最後手段：路徑前綴**
   - 以最長共同前綴目錄做分割

## 強制隔離規則
以下類型若大量改動，通常獨立成 chunk：
- DB migration / schema 改動
- Auth / security / crypto / key store
- 支付/扣款/交易結果頁（風險高）
- 分析/埋點（analytics）大量改動（容易影響商業指標）
- 大型 refactor（例如 package rename、API 大範圍替換）

## Token 控制
- 預設 MAX_TOKENS=12000（字元/4 粗估）
- chunk 目標：每段 6k–12k tokens（讓 model 有餘裕寫出「有行動性」的 review）
- 若單一檔案就超過上限：
  - 仍保留 unified diff 全文
  - base/head 全文可截斷，保留檔頭（import/package）+ 被改動區塊上下文
  - 在 manifest 記錄「截斷」並在總報告的限制中明示
