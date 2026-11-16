# 設定與 Helper 介面

本文件只放底層 schema、儲存與 CLI 契約。使用者互動見 `wizard-ux.md`。

## 儲存與繼承

- Global：`${XDG_DATA_HOME:-$HOME/.local/share}/create-git-branches/global.json`
- Project：同根目錄 `projects/<project-key>.json`
- 上一版：`global.previous.json` 或 `projects/<project-key>.previous.json`

`project-key` 優先由 normalized origin URL 產生，否則使用 repo 絕對路徑；搭配 repo 名稱與 SHA-256 前 12 碼。Effective config 依「內建基底 → global → project」合併；object 遞迴合併，array/scalar 由後者取代，最後完整驗證。Project 專屬設定永遠優先於 global 預設。

寫入使用同目錄暫存檔、`fsync` 與 `os.replace`。每次 set/update 覆寫前保存單一上一版；reset 將被刪除版本移到上一版；restore 交換目前與上一版，因此可再次復原操作。

`config set` 是整份 scope 覆寫，所以新增、修改、刪除 profile 都不需要額外的寫入子命令：組出候選 JSON → `config preview` → `config set` 即可。但合併是遞迴的，**project scope 無法刪除 global 已定義的 profile 或 target**，只能覆蓋同名 key；要真正移除必須改 global scope。

## Schema version 1

既有設定不需 migration。`presentation` 為新增的可選欄位：

```json
{
  "version": 1,
  "naming": {
    "template": "s{sprint}_{slug}",
    "ascii": true,
    "lowercase": true,
    "separator": "_",
    "candidate_count": 3
  },
  "variables": {
    "owner": {"description": "branch owner", "required": false},
    "sprint": {"description": "sprint number", "required": false, "default": "182"}
  },
  "targets": {
    "stg": "stg/{base}",
    "ut": "ut/{base}",
    "feature": "{owner}/feature/{base}"
  },
  "profiles": {"feature": ["stg", "ut", "feature"]},
  "defaults": {"profile": "feature", "remote": "origin", "checkout": false},
  "push": {"atomic": true, "set_upstream": true},
  "presentation": {
    "profile_labels": {"feature": "功能開發"},
    "target_labels": {"stg": "共同整合", "ut": "自動測試", "feature": "個人功能"}
  }
}
```

允許 placeholders：`base`（只限 target）、`slug`、`ticket` 與已宣告 variables。所有 target 必須含 `{base}`；profile 只能引用存在 target；label 只能引用存在 key；候選數至少 3；separator 只能是 `-` 或 `_`。

`variables.<name>.default` 為選填，展開時作為該變數的預設值（本次傳入的 `--var` 優先）；`config update-sprint` 寫入的就是 `variables.sprint.default`。`naming.template` 全域只有一條，所有 profile 共用 —— 需要不同名稱時，長期規則走「變更名稱規則」，單次需求走建立流程的「自訂名稱」（由 `validate-base` 驗證）。

## 唯讀介面

```bash
# Effective config、來源、路徑與 previous 路徑
python3 <script> config show --repo <repo>

# 一次列出全部組合；建立流程與回訪畫面用這個，不要用 show + N 次 expand
python3 <script> config options --repo <repo>
python3 <script> config options --repo <repo> --slug login_flow --var sprint=183

# 只讀掃描 local 與現有 remote-tracking refs；不 fetch
python3 <script> config discover --repo <repo> --limit 3

# 模擬指定 scope，驗證並展開所有組合；零寫入
python3 <script> config preview --repo <repo> --scope project \
  --file <candidate.json> --slug login_flow --var sprint=182 --var owner=jason

python3 <script> config validate --file <candidate.json>

# 展開單一組合；設定有多組時 --profile 為必填
python3 <script> expand --repo <repo> --profile feature --slug login_flow --var sprint=183
```

設定超過一組 profile 而未帶 `--profile` 時，`expand` 直接以 exit code 2 失敗並指向 `config options`。這是為了讓「不得靜默套用 `defaults.profile`」成為機制保證，而非只靠提示詞。恰好一組時才會沿用 `defaults.profile` 並自動選取。

`options` 依 profile 名稱排序回傳每一組的 `name`、`label`、`is_default`、`targets`、`target_labels`、`template_branches`，另有 `default_profile`、`profile_count`、`naming`、`variables`、`defaults`、`push`、`sources` 與設定檔路徑。`--slug` 可省略：省略時只回 `template_branches`（含 `{base}` 佔位）供回訪摘要使用；帶 `--slug` 與 `--var` 才另外回 `base`、`branches` 與 `naming.example_base`。

`options` 與 `preview` 的失敗語意刻意不同：`preview` 任一 profile 無法展開就整批阻擋，因為它守的是儲存；`options` 走的是建立路徑，單一 profile 無法展開時只標記該項 `expandable: false` 並列出 `missing`（缺少的 placeholder）與 `error`，其餘組合照常回傳，避免某一組缺變數就讓整個選單消失。

`discover` 只回傳至少重複兩個工作名稱的組合，包含 templates、實際 ref 證據、出現次數及最近時間；先依最近週排序，同週再依次數排序。首頁用 limit 3，「顯示更多」改用 limit 5。建議永不自動儲存。

`preview` 會保留另一 scope 及其優先順序，驗證合併結果，並展開每個 profile。任何缺值、無效名稱或重複結果均阻擋儲存。

## 寫入介面

Agent 只能在使用者完成白話選單確認後，內部帶入技術 confirmation：

```bash
python3 <script> config set --repo <repo> --scope global|project --file <candidate.json>
python3 <script> config update-sprint --repo <repo> --scope global|project --value 183 --confirm APPLY
python3 <script> config reset --repo <repo> --scope global|project --confirm RESET

# 第一次不帶確認只預覽；使用者確認後才執行
python3 <script> config restore --repo <repo> --scope global|project
python3 <script> config restore --repo <repo> --scope global|project --confirm RESTORE
```

不得要求使用者輸入 `APPLY`、`RESET` 或 `RESTORE`。
