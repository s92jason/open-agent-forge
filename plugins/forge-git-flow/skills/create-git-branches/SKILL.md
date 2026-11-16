---
name: create-git-branches
description: |
  從同一個經使用者確認的 Git 版本安全建立多條相關 branch，並可在完整預覽與再次明確確認後選擇性 atomic push。使用者只要描述需求；首次使用會從既有 branch 範例推導規則並接著完成原需求。當使用者輸入 `/create-git-branches [ticket 或需求]`、`/create-git-branches settings`，或說「幫我建立多條 branch」「批次建立分支」「設定 branch 規則」時使用。
allowed-tools: Bash(git:*) Bash(python3:*) Read Write AskUserQuestion
---

# Create Git Branches

從同一個確認過的 source SHA 建立一組 branch。讓使用者看白話結論，也保留完整技術資訊；將判定與 mutation 委派給 `scripts/create_git_branches.py`。所有路徑以本檔所在目錄解析。

開始前讀取：

- 首次設定、已設定的回訪畫面、`settings` 或任何規則變更：`references/wizard-ux.md` 與 `references/configuration.md`
- 建立或 push：`references/safety-contract.md`

## 不可違反的規則

1. 不套用未經確認的建議，也不要求使用者閱讀或編輯 JSON。
2. 首次設定儲存後接續原本的建立需求；只有取消才停止。變更組合或名稱規則後同樣接續。
3. 有多組 branch 組合時，不得靜默套用 `defaults.profile`。必須列出全部組合並取得明確選擇；`defaults` 只作為「上次使用」標記。每次建立都要讓使用者看見自己有哪些組合、可以新增或修改。
4. 不自動 fetch。只有使用者明確要求才 fetch；fetch 後重新 inspection 並重新確認 source。
5. source 確認前零 Git mutation；branch 清單確認前零 local ref mutation。
6. 所有 local branch 固定由同一個完整 SHA 建立，使用腳本的 atomic `git update-ref` transaction。
7. 預設不 push、不 checkout。絕不 force、delete 或自動覆蓋 local/remote collision。
8. Push 前顯示 exact remote、exact subset、SHA、upstream 行為與完整命令，並取得當下明確確認。remote、subset 或 SHA 改變即重新確認。
9. Atomic push 失敗或不支援時停止。只有使用者改選逐條 push、看過部分成功風險與命令、再次確認後才使用 sequential。

## 呈現契約

每個畫面依序顯示：

1. 一句白話結論與下一步。
2. 完整 branch 名稱與相關 ref、SHA、remote、URL、JSON 或 command；不可摺疊或省略。

面向使用者稱「branch 組合」「名稱規則」「每次變動的內容」。只有在緊接著解釋或展示底層 JSON 時才使用 `profile`、`target`、`template` 等 schema 名稱。

## 流程

### 1. 設定

執行 `config options --repo <repo>`。

- `configured: false`：明示「約一分鐘完成，儲存後會接著建立 branch」，依 `wizard-ux.md` 執行首次精靈。
- 已設定：**先顯示現況摘要**（每一組的白話名稱與 `template_branches`、名稱規則與範例、套用範圍與 exact 設定檔路徑），再提供入口選單。
- `settings`：同一份現況摘要與入口選單，差別只在完成後不接續建立。

```text
[1] 直接開始建立
[2] 變更 branch 組合（新增／修改／刪除）
[3] 變更名稱規則
```

絕不跳過這個畫面直接進入來源確認。使用者必須每次都看見自己有哪些組合、以及可以增刪改。若使用者一開始就明講要改規則（例如「Sprint 改成 183」「新增一組只建立 stg 和 qa」），直接跳到對應子流程，不必先顯示選單。選 2 或 3 完成儲存後，直接回到本次建立需求的來源畫面繼續，不要求重新輸入。

任何儲存都先對 project 與 global 候選執行 `config preview`，展示目前值及兩種套用結果的完整 branch 與 JSON，再詢問「只套用目前專案」或「設為其他專案的預設規則」。選定後顯示白話摘要、所有實際 branch、每次詢問值、push/checkout、範圍、路徑及完整 JSON。選項固定為「儲存並繼續／返回調整／取消」。

### 2. 從哪個版本開始

執行：

```bash
python3 <skill-dir>/scripts/create_git_branches.py inspect --repo <repo> --source <ref>
```

先說「這些 branch 將從哪個版本開始」，再顯示 source ref、完整 SHA、commit subject、upstream、ahead/behind 與 dirty 狀態。dirty 時明示未提交內容不會包含。要求確認 exact SHA；ref 後續移動仍只用已確認 SHA。

### 3. 決定名稱與組合

先定名稱：從 ticket/需求抽取 ticket ID、Sprint 與英文主題，只追問名稱規則實際引用但仍缺少的值。產生至少 3 個英文 ASCII、小寫候選，選單固定包含「自訂名稱」與「依回饋重新產生」；自訂值一律用 `validate-base` 驗證。

再選組合：執行 `config options --repo <repo> --slug <slug> --var <n=v>`，列出**全部**組合與各自完整展開的 branch。

- `is_default` 的那組標「（上次使用）」，但仍要明確選擇；只有 `profile_count` 為 `1` 時才自動選取並明示。
- `expandable: false` 的組合照常列出，標示還缺哪些值（`missing`），使用者選到才追問。
- 選單末尾固定提供「新增一組並存起來」，走 `wizard-ux.md` 的新增子流程，儲存後回到本步驟。

要不同的 branch 組合就新增一組存起來，之後可重複選用；不提供只用一次、不回寫的臨時增減。

### 4. Local 預覽與建立

用 `expand --profile <選定組合>` 取得權威展開結果（`--profile` 為必填；步驟 3 的 `config options` 結果只用於呈現），再用 `local-plan --source-sha <confirmed-full-sha> --branch <name> ...` 唯讀預檢。先翻譯狀態：

- `create`：將建立。
- `reuse`：已存在且版本相同，可直接使用。
- `collision`：名稱已指向不同版本，整批停止。

同時列出每條完整 branch、ref 與 SHA。取得完整清單確認後才執行 `create-local`。回報 created/reused/skipped、source SHA 與目前 checkout，然後詢問是否查看 push 預覽；預設否。

### 5. Push 與 checkout

讓使用者選 exact subset，再執行 `push-plan`。先說會上傳哪些 branch，再列 remote 名稱與 URL、subset、每條 SHA、upstream 行為與完整 atomic command。只接受：

```text
[1] 確認 push 上述 N 條 branch
[2] 調整 push 清單
[3] 不 push
```

選 1 後才以原 plan file 執行 `push --confirm`；選 2 重做 plan；模糊回答不執行。Push 成功、取消或失敗後才顯示 checkout 選單。預設保持原 checkout，只有選定 branch 才執行 `git switch <branch>`。
