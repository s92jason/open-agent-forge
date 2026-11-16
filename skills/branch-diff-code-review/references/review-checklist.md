# Review checklist（檢查清單）

## 必查（P0 風險）
- 變更是否可能造成 crash（NPE、Index、IllegalState、錯誤的 lifecycle）
- API/資料格式變更是否向後相容
- 安全性：敏感資料是否被記錄、傳輸、或存到不該去的地方
- 權限/認證/授權流程是否被繞過
- 金流/交易/訂單狀態機是否存在「重複扣款」「狀態不一致」「回補漏掉」風險
- 異常處理是否會吞錯誤、造成無法觀測

## 建議查（P1）
- 架構：責任分層是否清楚（UI/VM/UseCase/Repo/Api）
- 可測性：是否容易寫單元測試、是否需要抽介面/依賴注入
- 效能：不必要的重複計算、IO 在主執行緒、列表效能（Recycler/Compose）
- 可維護性：命名、重複邏輯、複雜度、註解是否解釋「為什麼」
- 國際化/無障礙：字串資源、contentDescription、觸控區域、字體縮放

## 加分項（P2）
- 日誌與監控：關鍵路徑有可觀測性（但避免敏感資訊）
- 錯誤訊息對使用者友善
- 可讀性：一致的 style、清楚的 domain vocabulary

## 預設排除（除非使用者要求）
- `**/build/**`, `**/.gradle/**`, `**/.idea/**`
- 大型 lock 檔（`package-lock.json`, `yarn.lock`, `pnpm-lock.yaml`）
- 二進位：png/jpg/mp4/keystore/aab/apk/zip/…
- 產物或自動生成：`**/generated/**`, `**/build/generated/**`

> 注意：排除不代表不重要，只代表「用 branch diff review 的性價比低」；若屬風險路徑（安全/支付/登入）仍應強制納入。
