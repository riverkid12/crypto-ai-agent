# crypto-ai-agent — Design Spec

- **Date**: 2026-05-30
- **Owner**: Y (riverkid)
- **Status**: Approved by user on 2026-05-30, pending implementation plan
- **Related projects**: `us-stock-ai-agent`(架構藍本)、`chat-notify-hub`(通知層)

---

## 1. 一句話

Cowork(Claude Desktop schedule)每天定時做策略決策、寫進雲端 DB;GitHub Actions cron 24/7 讀規則、監價、下單到單一交易所(Binance);本機是「看 + 改策略」的控制台,任何時候開機都可以。電腦不開機,雲端照跑、不漏單。

## 2. 動機與設計約束

| 約束 | 影響 |
|---|---|
| 使用者電腦不會 24/7 開機 | 執行層不能放本機,必須在雲端 |
| 不使用付費 LLM API,推理走 Claude Desktop schedule(Max 訂閱) | AI 思考是「排定的批次」,不是「即時」。設計必須把策略決策(AI)與規則執行(純程式)分開 |
| 不使用其他付費 API | 雲端排程、DB、通知全走免費額度。交易所 API 本身免費 |
| 已有 stock 工作流(Cowork + 本機 batch + 檔案橋樑) | 鏡像同一架構降低切換成本,但「本機執行」換成「雲端執行」 |
| Crypto 24/7,股市有開盤時間 | 執行層的 cron 間隔比 stock 短(5 分鐘 vs 一天一次),且全週無休 |

## 3. 高層架構

```
┌─ Cowork(Claude Desktop schedule, 每日 1–2 次)──────┐
│ 1. 拉行情(yfinance / CoinGecko / Binance public)    │
│ 2. 跑 Claude 策略推理                                 │
│ 3. 寫 decisions/<date>.json 到 mounted folder        │
│    (Cowork sandbox 連不到第三方 API,只能寫檔)        │
└─────────────────────────┬─────────────────────────────┘
                          │ (mounted folder = C:\Projects\crypto-ai-agent\)
                          ▼
┌─ 本機 post-Cowork 同步(緊接 Cowork,~5 分鐘)─────────┐
│ 1. 讀 decisions/<date>.json                           │
│ 2. 寫入 Turso(signals 表,UPSERT 覆蓋同 strategy)    │
│ 3. git commit & push(留審計軌跡)                    │
│ 4. 推 chat-notify-hub:今日決策摘要                   │
│ (laptop 早上短暫開機完成這 ~5 分鐘即可關機)           │
└─────────────────────────┬─────────────────────────────┘
                          │ (write)
                          ▼
              ┌─── Turso (cloud libSQL) ───────┐
              │  strategies / signals / orders │
              │  positions / pnl_daily / events│
              │  control(kill switch 等)       │
              └─────────────┬──────────────────┘
                            │ (read+write)
              ┌─────────────┴───────────────┐
              ▼                             ▼
   ┌─ GHA `exec_tick.yml`(每 5 分鐘)┐  ┌─ 本機控制台 ──────┐
   │ 0. 讀 control.kill_switch        │  │ _START_HERE/*.bat │
   │ 1. 讀 active signals             │  │ 看報告、改策略、   │
   │ 2. 抓現價、判 trigger            │  │ 緊急停止          │
   │ 3. 下單 → exchange adapter       │  │ 任何時候開機都可 │
   │ 4. 寫回 orders/positions/events  │  └───────────────────┘
   │ 5. 觸發/錯誤推 chat-notify-hub   │
   └──────────────────────────────────┘
   ┌─ GHA `exec_daily.yml`(每日 23:55 TW)┐
   │ 對帳、結算 pnl_daily、產報告、推 Discord │
   └────────────────────────────────────────┘
```

**三個現實限制決定這個架構**(對應 stock 專案架構文件第 33 行的同類型限制):
1. 本機不能 24/7 → 執行層必須放雲端。
2. AI 推理只能批次跑(Claude Desktop schedule)→ AI 設規則、Python 執規則,不在 hot path 上呼叫 LLM。
3. Cowork 沙盒對第三方 API 出口受限 → Cowork 只能寫檔到 mounted folder;Turso、Discord、交易所等任何外網呼叫都必須由本機 post-Cowork 步驟或 GHA 代勞。

## 4. 技術選型

| 層 | 選 | 替代 | 理由 |
|---|---|---|---|
| 雲端排程 | **GitHub Actions cron** | Cloudflare Workers、Oracle Free VM | Python 原生支援、零學習成本、免費額度足夠(5 分鐘 cron ≈ 1500 min/月 < 2000) |
| 雲端 DB | **Turso (libSQL)** | Cloudflare D1、Supabase | SQLite 介面、本機開發可指向同一份 schema、9GB 免費、Python SDK 成熟 |
| 交易所(預設) | **Binance(testnet → live)** | Bybit、OKX、台灣 MAX | `python-binance` SDK 完整、testnet 真實模擬、流動性最大;若 KYC/地區受限,透過 adapter 層可換 |
| 行情資料 | **Binance public REST + WebSocket** | CoinGecko 補非交易標的 | 都免費、no auth |
| 通知 | **chat-notify-hub**(現有) | — | 重用,不重造 |
| Secrets | **GitHub Secrets**(雲端) + 本機 `.env` | — | 跟 stock 一致 |
| 本機控制台 | **Windows batch + Python** | — | 跟 stock 一致,使用者已熟悉 |

## 5. 倉庫結構(刻意鏡像 us-stock-ai-agent)

```
C:\Projects\crypto-ai-agent\
├── _START_HERE\                    控制台 .bat(中文檔名、英文內容、UTF-8 無 BOM、chcp 65001)
│   ├── 1_調整策略.bat               開 UI 改 strategy_config.json
│   ├── 2_立即同步帳戶.bat           手動觸發 sync workflow
│   ├── 3_立即下單.bat               手動觸發 exec_tick workflow(workflow_dispatch)
│   ├── 4_緊急停止_暫停下單.bat      寫 Turso control.kill_switch = true
│   ├── 5_解除緊急停止_恢復下單.bat  寫 Turso control.kill_switch = false
│   ├── 6_查看今日結果.bat           開啟今日 post_execution_<date>.md
│   ├── 7_開啟資料夾.bat
│   └── 說明.txt
├── .github\workflows\
│   ├── exec_tick.yml               cron: 每 5 分鐘
│   ├── exec_daily.yml              cron: 每日 23:55 TW (15:55 UTC)
│   └── exec_manual.yml             workflow_dispatch:手動觸發、可帶 dry-run flag
├── pipeline\                       Cowork 端(策略分析,跑在 Cowork sandbox)
│   ├── scan.py                     拉行情、計算技術指標
│   ├── strategy.py                 策略邏輯(MVP: trend_majors)
│   ├── risk.py                     部位大小、停損計算
│   ├── claude_reasoning.md         給 Claude 的 prompt 模板
│   └── write_decisions.py          寫 decisions/<date>.json(本機檔,不打外網)
├── bridge\                         本機 post-Cowork 同步(早上跑 ~5 分鐘)
│   ├── sync_signals.py             讀 decisions/<date>.json → Turso UPSERT signals
│   ├── push_repo.py                git commit & push(審計軌跡)
│   └── notify_decisions.py         推 chat-notify-hub 今日摘要
├── executor\                       GHA 端(下單執行,跑在 GitHub Actions)
│   ├── tick.py                     主迴圈:讀 signals → 判 trigger → 下單
│   ├── matcher.py                  signal vs 現價匹配邏輯
│   ├── circuit_breaker.py          kill switch + 每日損失上限 + API 失敗熔斷
│   ├── reporter.py                 對帳、結算、產 post_execution_<date>.md
│   └── sync_positions.py           從交易所拉 positions 寫回 Turso
├── adapters\
│   ├── exchanges\
│   │   ├── base.py                 抽象介面:get_price/place_order/get_balances/cancel
│   │   ├── binance.py              python-binance 包裝,支援 testnet flag
│   │   └── _fake.py                測試用 fake exchange(in-memory)
│   └── notify\
│       └── chat_notify_hub.py      呼叫現有 chat-notify-hub
├── schema\
│   ├── 001_init.sql                建表
│   ├── 002_seed.sql                預設 control 值 + universe
│   └── migrate.py                  套用 .sql 到 Turso
├── strategies\                     = stock 的 profiles
│   └── trend_majors\
│       ├── strategy_config.json    參數(均線週期、突破閾值、size_pct 等)
│       ├── universe.json           交易標的(BTCUSDT/ETHUSDT/SOLUSDT)
│       └── README.md
├── state\                          本機 cache(讀 Turso 後存一份,給 batch 顯示用)
├── logs\
├── docs\
│   ├── superpowers\specs\          設計文件
│   └── 專案架構.md                  類似 stock 的總覽,完成 MVP 後寫
├── tests\
│   ├── test_executor.py            使用 fake adapter
│   ├── test_matcher.py
│   ├── test_circuit_breaker.py
│   └── test_strategy.py
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

**一個 strategies 子資料夾 = 一個獨立策略**:完全套用 stock 的 profile 模型。MVP 只開 `trend_majors`,未來加 `mean_reversion`、`breakout` 都是新增資料夾;executor 用 strategy_id 索引到對應的參數,無需改主邏輯。

## 6. 資料模型(Turso schema)

```sql
-- 策略註冊表
CREATE TABLE strategies (
  id           INTEGER PRIMARY KEY,
  name         TEXT UNIQUE NOT NULL,
  params_json  TEXT NOT NULL,
  active       INTEGER NOT NULL DEFAULT 1,
  updated_at   TEXT NOT NULL
);

-- AI 寫出的進場規則,executor 讀取後 trigger
CREATE TABLE signals (
  id            INTEGER PRIMARY KEY,
  strategy_id   INTEGER NOT NULL REFERENCES strategies(id),
  symbol        TEXT NOT NULL,
  side          TEXT NOT NULL,           -- long / flat(MVP 不做 short)
  entry_price   REAL,                    -- NULL = market entry
  stop_price    REAL,
  target_price  REAL,
  size_usdt     REAL NOT NULL,
  status        TEXT NOT NULL,           -- pending / triggered / filled / cancelled / expired
  reason        TEXT,                    -- Claude 寫的進場理由(供報告引用)
  expires_at    TEXT,                    -- 此 signal 何時失效(預設 +24h)
  created_at    TEXT NOT NULL
);
CREATE INDEX idx_signals_status ON signals(status, expires_at);

-- 實際送出的訂單
CREATE TABLE orders (
  id                INTEGER PRIMARY KEY,
  signal_id         INTEGER REFERENCES signals(id),
  exchange_order_id TEXT,
  symbol            TEXT NOT NULL,
  side              TEXT NOT NULL,       -- buy / sell
  qty               REAL NOT NULL,
  price             REAL,                -- 市價單為 NULL
  type              TEXT NOT NULL,       -- market / limit / stop_market
  status            TEXT NOT NULL,       -- new / partial / filled / cancelled / failed
  fill_qty          REAL DEFAULT 0,
  fill_price        REAL,
  fee_usdt          REAL DEFAULT 0,
  created_at        TEXT NOT NULL,
  filled_at         TEXT
);

-- 當前持倉(每個 symbol 一行,upsert)
CREATE TABLE positions (
  symbol           TEXT PRIMARY KEY,
  qty              REAL NOT NULL,
  avg_entry        REAL NOT NULL,
  current_price    REAL,
  unrealized_pnl   REAL,
  updated_at       TEXT NOT NULL
);

-- 每日損益
CREATE TABLE pnl_daily (
  date             TEXT PRIMARY KEY,     -- YYYY-MM-DD(TW timezone)
  realized_pnl     REAL NOT NULL,
  unrealized_pnl   REAL NOT NULL,
  equity           REAL NOT NULL,
  trades_count     INTEGER NOT NULL
);

-- 控制旗標(kill switch、上限、暫停等)
CREATE TABLE control (
  key         TEXT PRIMARY KEY,
  value       TEXT NOT NULL,
  updated_at  TEXT NOT NULL
);
-- seed(全部都是預設值,可隨時改 Turso):
--   風控
--   (kill_switch, false)
--   (max_per_trade_usdt, 500)
--   (max_daily_loss_usdt, 300)
--   (max_open_positions, 3)
--   (max_position_per_symbol, 1)
--   (api_fail_threshold, 3)
--   (slippage_max_pct, 0.01)
--   signal
--   (signal_default_expiry_hours, 24)
--   時間 (TW)
--   (cowork_decision_time_tw, 21:00)
--   (bridge_run_time_tw, 21:05)
--   (daily_report_time_tw, 23:55)
--   (exec_tick_interval_minutes, 5)
--   通知
--   (notify_dedup_window_minutes, 10)

-- 稽核 / debug log
CREATE TABLE events (
  id            INTEGER PRIMARY KEY,
  type          TEXT NOT NULL,           -- signal_in / order_placed / fill / circuit_open / error / ...
  payload_json  TEXT NOT NULL,
  created_at    TEXT NOT NULL
);
CREATE INDEX idx_events_created ON events(created_at);
```

## 7. 工作流(每日 timeline,TW 時區)

| 時間 | 誰 | 做什麼 | 產出 |
|---|---|---|---|
| **21:00** | Cowork (Claude Desktop schedule) | 拉行情 → Claude 推理 → 寫 `decisions/<date>.json` 到 mounted folder | 本機 decisions/<date>.json |
| **21:05** | 本機 `bridge/`(Claude Desktop schedule 鏈下一步)| 讀 decisions → UPSERT Turso signals → git push → 推 chat-notify-hub | Turso signals 表更新、Discord 摘要 |
| **21:10 後**(laptop 可關)| — | 雲端接手 | — |
| **每 5 分鐘** | GHA `exec_tick.yml` | 讀 control + active signals → 抓現價 → trigger 滿足者下單 → 寫回 | `orders`、`positions`、`events` 更新 |
| **21:00 後即時** | GHA `exec_tick.yml`(同一 cron) | 觸發新 fill → 推 chat-notify-hub | Discord 通知 |
| **每 5 分鐘**(同上) | GHA `exec_tick.yml` | 監持倉,觸發 stop / target → 平倉 | 同上 |
| **23:55** | GHA `exec_daily.yml` | 對帳、結算 pnl_daily、產 post_execution_<date>.md、推總結 | 報告 + Discord 摘要 |
| **任何時候** | 本機 `_START_HERE\*.bat` | 看報告、改 strategy_config、緊急停止 | — |

**laptop 開機需求**:每天約 21:00–21:10(~10 分鐘)為了 Claude Desktop schedule 觸發 Cowork + 本機 bridge。完成後可關機,其餘 23.5 小時雲端自跑。**時段可在 control 表調整**(改成早上、午休、深夜都行,但要對應改 Claude Desktop schedule 設定)。

**所有時間都是預設值,可調**:`cowork_decision_time_tw`、`bridge_run_time_tw`、`daily_report_time_tw`、`exec_tick_interval_minutes` 都寫在 control 表,改 Turso 即生效(GHA 下次 tick 讀新值)。

**邊界條件:**
- 若使用者當天決策時段沒開電腦,Cowork 不會跑、bridge 也不會跑,Turso signals 表保持上一份。GHA 仍會繼續執行未過期的 signals 與管理現有部位(包括停損)。
- 若 GHA 連續失敗(API 限流、Turso 抖動),events 累計 ≥ 3 → 寫 circuit_open event + Discord 警報,該 tick 該 symbol skip。
- 若 strategies.active=0,executor 不開新倉但仍管現有部位(不影響停損)。

## 8. 風控規則(executor 內寫死,不可被 strategy 覆寫)

**所有規則都是預設值,改 Turso `control` 表即生效**(executor 每 tick 重讀)。下表「預設」=出廠值,「key」=control 表的 key。

| 規則 | key | 預設 | 行為 |
|---|---|---|---|
| Kill switch | `kill_switch` | false | true → **擋所有新開倉**;**永遠允許風險縮減動作**(平倉、停損、止盈、cancel)|
| 單筆上限 | `max_per_trade_usdt` | 500 | 超過直接拒下 |
| 每日虧損上限 | `max_daily_loss_usdt` | 300 | 當日 realized P&L ≤ -此值 → 自動 set kill_switch=true |
| 同時持倉上限 | `max_open_positions` | 3 | 已達上限不開新倉 |
| 單一 symbol 持倉上限 | `max_position_per_symbol` | 1 | 不加碼 |
| API 失敗熔斷 | `api_fail_threshold` | 3 | 同 symbol 同 tick 失敗達此數 → 跳過、寫 event、推警報 |
| Slippage 上限 | `slippage_max_pct` | 0.01 (1%) | 市價單預估價差超過 → 拒絕下單 |
| Symbol 白名單 | — | 來自 `strategies.params_json.universe` | 不在 universe 內的 symbol 一律拒下(不可繞過)|

**核心原則**:
1. 任何資金安全的判斷都在 `circuit_breaker.py`,不在 `strategy.py`。AI 寫策略可以亂寫,executor 是最後一道閘門。
2. Kill switch 是「煞車」不是「方向盤拔掉」 — 任何 **降低風險** 的動作(平倉、停損、止盈、cancel pending)在 kill switch 開著時仍會執行;只有 **新增風險** 的動作(開新倉、加碼)被擋。這樣才能避免「按下緊急停止後反而沒人幫你停損」的死亡螺旋。
3. **Symbol 白名單例外**:這條故意不放 control 表,只能透過修改 strategy 設定才能加新標的(改完要 Cowork 重跑寫 signal),避免「半夜被 social engineering 把白名單關掉直接打超出範圍的標的」。

## 9. 通知設計(透過 chat-notify-hub)

| 事件 | 嚴重度 | 內容 |
|---|---|---|
| 新 signal 寫入 | info | 摘要:標的、方向、entry/stop/target、reason 一句 |
| 訂單下出去 | info | symbol、side、qty、預估價 |
| 訂單成交 | info | symbol、side、fill_qty、fill_price、fee |
| 停損/止盈觸發 | warn | symbol、出場價、本筆 P&L |
| Kill switch 自動觸發 | error | 原因(daily loss / circuit) |
| API 連續失敗 | error | symbol、最後一次錯誤訊息 |
| Daily summary(23:55) | info | 當日 trades、realized P&L、equity、現有部位列表 |

**反 spam**:同訊息(同 type + 同主要欄位)10 分鐘內去重,參考 stock CLAUDE.md 第 5 條「先檢查、送成功才記」設計 deduper。

## 10. MVP 範圍

**in:**
- 1 個交易所(Binance,testnet 起手)
- 1 個策略(`trend_majors`):BTC/ETH/SOL,每日重評估,均線突破 + 簡單趨勢分數
- Spot 現貨、Long-only
- 完整風控(8 條規則)
- chat-notify-hub 通知
- 本機控制台 7 個 .bat
- 每日報告(post_execution_<date>.md)

**out(後續再加):**
- 多交易所、多策略並行
- Short / 槓桿 / 合約
- Live 真錢(testnet 滿 2–4 週 P&L 穩定才切)
- Web dashboard(MVP 看 .md 報告)
- 跨 profile 總覽報告
- Telegram(目前只 Discord)

## 11. 落地階段

| 階段 | 範圍 | Exit criteria |
|---|---|---|
| **P0 骨架**(~3 天) | repo、Turso 接通、schema migrate、fake exchange adapter、e2e mock 流程跑得通 | `pytest tests/ -v` 全綠;能在本機跑 `python -m executor.tick --fake` 看到模擬交易 |
| **P1 Binance testnet 接通**(~3 天) | `adapters/exchanges/binance.py`、實連 testnet、Cowork 手動寫 1 個假 signal、GHA 觸發、收到 testnet fill | 連續 3 天 cron 跑無 critical error,Discord 收得到通知 |
| **P2 Claude 策略推理**(~5 天) | `pipeline/scan.py`、`strategy.py`、`claude_reasoning.md` prompt、Cowork schedule 接好 | 連續 5 天每天有合理 signal,人工 review 不亂發 |
| **P3 風控 + 控制台**(~3 天) | `circuit_breaker.py`、_START_HERE 全部 7 個 .bat、緊急停止真的能停 | 手動測試:寫入錯誤、跑損、按緊急停止,行為符合預期 |
| **P4 觀察期**(2–4 週) | testnet 跑滿、追 P&L、調參、修 bug | 連續 2 週無 critical bug、P&L 不離譜 → 評估是否切 live |

**P4 之後再決定** 是否切 live、是否加第二個策略。

## 12. 與既有專案的互動

| 既有 | 怎麼用 |
|---|---|
| `us-stock-ai-agent` | 架構藍本。`adapters/`、`circuit_breaker`、`profiles → strategies` 概念都搬。**但程式碼不共用 repo**,以免兩邊耦合 |
| `chat-notify-hub` | 通知層直接呼叫。注意 stock CLAUDE.md 第 3 條:第三方 API 不能在 Cowork 內呼叫,Cowork 端要透過寫檔案 → 本機/GHA 中轉 |
| `social-media-scrapers` | 不直接耦合。未來如果策略要吃 Twitter 情緒,再從這邊拉資料 |

## 13. 風險與已知未解

| 風險 | 緩解 |
|---|---|
| GHA cron 漂移(實際排程可能 ±幾分鐘) | Tick logic 是 idempotent(讀現價→判規則→下單前再查持倉);漂移不影響正確性,只影響反應速度 |
| Turso 出包(downtime / 延遲) | Tick 內捕捉、寫 event、本次 skip;連續 3 次失敗推警報 |
| Binance testnet ≠ live(滑價、流動性) | P4 觀察期之後人工判讀;切 live 前先小額試 1 週 |
| Claude 寫出爛 signal(亂進場) | 風控 + universe 白名單兜底;每筆 signal 進 events log 可事後 review |
| API key 外洩 | 全進 GitHub Secrets,從不寫進 repo;.env.example 列名不列值 |
| 台灣 KYC / 監管 | 交易所選擇與額度由使用者決定;架構支援 adapter 切換 |

## 14. 開發紀律(從 stock 借,寫進 README)

1. **批次檔純 ASCII**:`.bat` 內容只用英文(stock CLAUDE.md 第 1 條)
2. **長檔走 heredoc**:Write tool 對 100+ 行有截斷風險(第 2 條)
3. **Cowork 不打第三方 API**:用 fake adapter 在 Cowork 測,真打留給本機/GHA(第 3 條)
4. **改完 .py 要 touch**:避免 .pyc 殘留(第 4 條)
5. **Deduper 拆 has_seen / mark_seen**:送成功才記(第 5 條)
6. **四連驗證**:`wc -l && tail -5`、`python -c import`、`compileall`、跑 fake adapter 測試(第 8 條)

---

## Appendix A:接下來的步驟

本 spec 經使用者拍板後,呼叫 `superpowers:writing-plans` 產出實作計畫,先做 P0(骨架)。
