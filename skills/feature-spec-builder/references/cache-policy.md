# Cache Policy

> 適用：feature-spec-builder Phase 1.5 Source Extraction。

## 規則：一條 + 一例外

```
規則：抓取 Figma / Axure 時，一律透過 `scripts/extract_with_cache.py`。
       Cache hit  → 跳過 extractor，直接用既有 JSON。
       Cache miss → 呼叫 extractor，產出新 JSON 與 .cache.json。

例外：Update menu A/B 對使用者本輪列出的每個 URL，加 `--bust-cache`。
       重列 URL 即表示使用者明示要 refetch。
```

沒有互動式詢問、沒有「強制重抓」對話指令。**Menu 動作本身就是 intent 宣告。**

## 檔案結構（per-link，content-addressed）

```
<repo-root>/.ai-artifacts/feature-spec-builder/<feature-name>/
├── figma/
│   ├── <8-char-hash>.json        # Figma 抽取結果
│   └── <8-char-hash>.cache.json  # metadata（fingerprint、fetched_at、output_sha256）
└── axure/
    ├── <8-char-hash>.json
    └── <8-char-hash>.cache.json
```

`<8-char-hash>` = `sha256("<source_type>|<url>|<page or empty>")[:8]`。同一 URL 永遠對應同一檔名，cache 命中天然成立。

## Cache hit 判定（七項全中）

1. `<hash>.json` 與 `<hash>.cache.json` 都存在
2. cache 內 `source_type` 與本次一致
3. cache 內 `source_url` 與本次一致
4. cache 內 `source_page` 與本次一致（Figma 才比；Axure 為空字串）
5. cache 內 `extractor_version` 等於目前 extractor 的 `EXTRACTOR_VERSION`（抽取邏輯改版即失效）
6. `(now - fetched_at) <= ttl_days * 24h`（預設 7 天）
7. 現存 JSON 的 sha256 等於 cache 內 `output_sha256`（完整性檢查）

任一不符 → MISS → 呼叫 extractor 重抓並覆寫。

> 第 5 項對應 CLAUDE.md「Cache 化原則 #1」：fingerprint 須含所有影響輸出的因素。
> 對「抽取輸出」而言，唯一會改變結果的版本因素是 `extractor_version`（隨 extractor 程式碼走）。
> `skill_version` 也寫進 cache metadata，但僅供觀察、**不參與失效判定**——skill 的編排版本不會改變
> extractor 吐出的 JSON。改 extractor 邏輯時記得進 `EXTRACTOR_VERSION`，cache 才會正確失效。

## 各模式如何使用

| 模式 / 場景 | 呼叫方式 |
|---|---|
| Create mode 抽取每個 link | `extract_with_cache.py {figma\|axure} "<url>" [--page "<p>"] --feature-dir <dir>` |
| **Update menu A/B 抽取每個 link** | **同上 + `--bust-cache`** |
| Update menu C/D/E/F/G | 不跑 Phase 1.5 |
| Code Sync mode | 不跑 Phase 1.5 |
| Phase 2 Reconcile 讀既有 JSON | 直接 `glob <feature>/figma/*.json`，不經 wrapper |

## stdout / stderr 約定

- `CACHE_HIT: <output_path>` → stdout，exit 0，未呼叫 extractor
- `EXTRACTED: <output_path>` → stdout，exit 0，已呼叫 extractor
- `CACHE_BUSTED: ...` / `CACHE_MISS (<reason>): ...` → stderr，僅供觀察
- 非 0 exit → extractor 失敗，依 `access-and-credential-handling.md` 處理

## TTL

預設 7 天，由 `cache_helper.py` 的 `DEFAULT_TTL_DAYS` 控制。**TTL 是防禦性 floor**：即使使用者沒重列 URL（沒走 A/B 路徑），7 天後也會強制重抓，避免遠端 Figma/Axure 被外部修改導致使用過時資料。

## 為何不需要「強制重抓」對話指令

- 使用者要強制重抓某個 link → 進 Update menu A/B 重列該 link（會 bust cache）
- 使用者要強制重抓全部 → `rm -rf .ai-artifacts/feature-spec-builder/`

兩種方式都比學一個新指令直覺。

## 不在 cache 範圍

- `~/.local/share/feature-spec-builder/<project-key>.json`（專案層設定）
- `FEATURE-SPEC.md`（最終產出）
- 本機 secret store（token / access code；macOS Keychain 或 0600 檔案）
