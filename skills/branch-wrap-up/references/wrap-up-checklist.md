# Branch Wrap-Up 收尾自檢清單

> 供 Step 5 Review Gate 在判斷「是否允許 commit」時的補充參考。
> 這些項目不是自動檢查的，而是提示 Claude 在 review 報告的 P0/P1 分類時應考量的面向。

---

## 必須通過才能 commit（P0 等級）

- [ ] 沒有 Null/NullPointerException 風險（存取前未做 null check）
- [ ] 沒有未處理的 Exception（空白 catch block 或吞掉 error）
- [ ] 沒有硬編碼的 API key、token、密碼（敏感資訊洩漏）
- [ ] 沒有破壞現有 API 合約（回傳值型別、欄位名稱、端點路徑）
- [ ] 金流/訂單/帳務邏輯沒有計算錯誤
- [ ] 認證/授權邏輯沒有繞過或遺漏

---

## 建議在 commit 前確認（P1 等級，影響 Review Gate 分數）

- [ ] 新增的函式/方法有基本測試覆蓋（至少 happy path）
- [ ] 沒有循環依賴或不合理的分層跨越
- [ ] 主要流程的錯誤狀態有明確的 UI/log 回饋
- [ ] 如有改動 DB schema，遷移腳本已加入且可回滾
- [ ] 如有新 API 端點，文件已更新
- [ ] 效能敏感路徑（列表渲染、DB 查詢）沒有引入明顯瓶頸

---

## 加分項（P2 等級，影響評分但不阻擋）

- [ ] log 輸出有助於未來排查問題
- [ ] 複雜邏輯有適當的行內說明（WHY，不是 WHAT）
- [ ] 邊界條件（空陣列、零值、最大值）有處理或明確說明不處理的原因
- [ ] 錯誤訊息對使用者友善（不是 raw error/stack trace）

---

## 收尾特別注意事項

- **TODO/FIXME**：所有新增的 TODO/FIXME 應該有 ticket 追蹤或明確說明預計處理時機
- **臨時性程式碼**：`// TEMP`、`// HACK` 標記的程式碼如果要帶進 PR，必須說明理由
- **Feature flag**：若有使用，確認預設狀態（開/關）符合預期
