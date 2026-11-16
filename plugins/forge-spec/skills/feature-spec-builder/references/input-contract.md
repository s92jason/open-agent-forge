# Input Contract

## Goal

定義使用者在啟用 Skill 時，至少要提供哪些資訊，才能穩定產出或更新 `FEATURE-SPEC.md`。

## Minimum required inputs

正式 spec 產出最低門檻：

- 至少一個設計來源：Axure link 或 Figma link

若兩者都缺：

- 視為核心來源不足
- 需要再次向使用者確認
- 不可直接產正式 spec

若只有其中一個：

- 可產出 spec，但缺少的來源對應章節標記 `[Source not provided]`
- 文件狀態至多為 `In Progress`

## Preferred input bundle

### 1. Feature basics

- Feature name
- 目標 repo 路徑或功能資料夾
- 這次是新功能或改版
- 若是改版，本次變更點是什麼

### 2. Axure inputs

至少提供：

- Axure 主流程連結

強烈建議提供：

- 主流程頁面
- 例外流程頁面
- 錯誤 / retry / back flow 說明
- 使用者補充：哪些 flow 已定稿、哪些待確認

### 3. Figma inputs

最低建議：

- File link
- Primary page link
- 至少 3 個 key frame links

強烈建議：

- Prototype link
- 非 happy path state frame links
- Dialog / bottom sheet frame links
- 使用者補充：
    - 哪些 frame 為正式稿
    - 哪些為探索稿
    - 哪些互動以 Axure 為準
    - 哪些視覺以 Figma 為準

### 4. API / data inputs

可選但建議：

- API doc link
- request / response 摘要
- 已知欄位與狀態碼
- 若未定，至少說明目前待確認

### 5. Optional code context

可選增強模式：

- 現有功能路徑
- 既有 `FEATURE-SPEC.md`
- 舊版畫面或 route 名稱
- ViewModel / state / use case 相關路徑

## Figma link granularity rules

- `File link`：整體設計檔範圍
- `Primary page link`：本次 backlog 範圍
- `Frame links`：精準分析目標
- `Prototype link`：主要互動流程

規則：

- 只有 file link：不足
- 只有 page link：勉強可開始，但需追問 key frame links
- 建議組合：
    - 1 個 file link
    - 1 個 primary page link
    - 1 個 prototype link（若有）
    - 3~6 個 key frame links

## Recommended user prompt format

```md
功能名稱：Spending Analysis Revamp
模式：更新既有 FEATURE-SPEC.md
目標路徑：app/src/main/java/.../spending/

Axure：
- 主流程：<link>
- 例外流程：<link>

Figma：
- File link：<link>
- Primary page link：<link>
- Prototype link：<link>
- Key frames：
  - Entry：<link>
  - Main：<link>
  - Empty：<link>
  - Error：<link>
  - Filter sheet：<link>

API：
- Summary：<link or text>
- 狀態：待確認 chart aggregation 欄位

補充：
- 這次主要改動在 filter flow 與 empty state
- 視覺以 Figma 為準，互動分支以 Axure 為準