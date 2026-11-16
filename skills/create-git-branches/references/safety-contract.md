# Git 與 Push 安全契約

## Source contract

- Inspection 是 read-only；不得 fetch。
- 顯示 ref 與完整 resolved SHA、subject、upstream/ahead-behind、dirty/untracked。
- dirty worktree 不阻擋，但必須標示未提交內容不在 branch 內。
- detached HEAD 合法，顯示為 detached；仍須確認 exact SHA。
- 使用者要求 fetch 時，fetch 後舊 inspection 失效，必須重新顯示與確認。

## Local ref contract

- 每個名稱先通過 `git check-ref-format --branch`，再檢查輸入重複與 local collision。
- 同名 local ref 指向 source SHA：reuse，不更新。
- 同名 local ref 指向不同 SHA：整批阻擋。
- 所有待建立 refs 透過單一 `git update-ref --stdin` transaction 的 `start`、`update ... 0000...`、`prepare`、`commit` 建立；任何一條失敗則全不建立。
- 不 checkout、不 delete、不 force。

## Push contract

`push-plan` 必須把 exact remote、branch subset、每條 local SHA、atomic/upstream 模式與 remote snapshot 寫入 plan JSON，並以 canonical JSON SHA-256 綁定。plan ID 只供腳本驗證，不要求使用者閱讀或輸入。

預覽需顯示：

- remote 名稱與 URL
- push/synced/blocked 的完整清單
- 每條 local SHA（正常情況應全部等於 confirmed source SHA）
- upstream 行為
- 實際 argv 等價命令

Remote 同 SHA 不重推；remote 不同 SHA 阻擋整批且不提供 force。執行 `push --confirm` 前重新檢查 local refs、remote URL 與 remote refs；任何 drift 使 plan 失效。

預設 atomic：`git push --atomic [--set-upstream] <remote> refs/heads/a:refs/heads/a ...`。遠端不支援時停止，不自動 fallback。若使用者改選 sequential，重新產生 `--mode sequential` plan，明示「前面成功、後面失敗」的部分成功風險，顯示每條命令，並再次取得相同簡單確認。

任何路徑都不得執行 force、delete、自動 fetch。Push 成功、取消或失敗後才可詢問 checkout。
