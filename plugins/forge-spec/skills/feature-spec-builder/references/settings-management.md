# Settings Management Mode

當使用者說以下觸發詞時，**進入設定管理模式，不執行 spec 產生**：

- 「查看 spec 設定」「查看專案設定」「show project settings」
- 「更新 coding standard」「更改 coding standard」「update coding standard」
- 「重設專案設定」「清除專案設定」「reset project settings」

## project-key 規則

project-key 取自 git repo 根目錄名稱，**必須經過 sanitize**：只保留 `[a-zA-Z0-9_-]`，其餘字元一律替換為
`_`。

例：`my_app_android` → `my_app_android`、`my project (v2)` → `my_project__v2_`

## 查看設定

讀取 `${XDG_DATA_HOME:-~/.local/share}/feature-spec-builder/{project-key}.json`，輸出：

```
目前專案設定（{project-key}）：
- Coding standard：{path or "（未設定）"}
  說明：{description}

可執行操作：A. 更新 coding standard  B. 重設所有設定  C. 離開
```

## 更新 coding standard

詢問新的路徑或說明，取得後寫入設定檔，覆蓋舊值。

## 重設設定

給出確認提示，使用者輸入「確認」後清除設定檔。下次產生 spec 時會重新詢問。
