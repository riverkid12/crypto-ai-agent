# crypto-ai-agent P1 Setup Guide

P1 之後,系統會 24/7 在雲端跑(GitHub Actions cron),你本機不用一直開。
這份文件是「從 0 到第一筆 testnet 成交」的完整步驟。

預計 30–60 分鐘可以做完。

---

## 1. Turso(雲端 SQLite)

1. 註冊:https://turso.tech(用 GitHub 登入最快)
2. 安裝 CLI(可選,Web UI 也能完成全部步驟):
   - Windows (PowerShell):`irm https://get.tur.so/install.ps1 | iex`
   - macOS / Linux:`curl -sSfL https://get.tur.so/install.sh | bash`
3. 登入並建 DB:
   ```bash
   turso auth login
   turso db create crypto-ai-agent --location nrt   # nrt = 東京;最近的 region
   ```
4. 取得 URL 與 token:
   ```bash
   turso db show crypto-ai-agent --url        # libsql://crypto-ai-agent-<you>.turso.io
   turso db tokens create crypto-ai-agent     # eyJ... (很長的 JWT)
   ```
5. 把 URL 和 token 記下來(待會兩個地方都會用到)。

## 2. Binance testnet

1. 開 https://testnet.binance.vision/,用 GitHub 登入
2. 「Generate HMAC_SHA256 Key」→ 取得 API Key 和 Secret
3. 預設你會有一些 testnet USDT / BTC;不夠的話點「Faucet」拿更多

## 3. Discord 通知(P1.5 新增,直連 Discord webhook 即可)

`CHAT_NOTIFY_HUB_URL` 自動偵測 URL 格式:
- 包含 `discord.com/api/webhooks` → 用 Discord embed 格式發送(✨ 漂亮的卡片)
- 其他 → 假設是 chat-notify-hub HTTP API,發送 `{type, severity, payload}` JSON

**選一個用**:

**選 A. Discord webhook(推薦,5 分鐘搞定)**
1. Discord 桌面版 → 你管理的任意 server → 挑/建一個收通知的頻道(例如 `#crypto-bot`)
2. 頻道齒輪 → Integrations → Webhooks → New Webhook
3. 取名(例如 `crypto-bot`)→ Copy Webhook URL → 長這樣:
   `https://discord.com/api/webhooks/<id>/<token>`
4. 把這個 URL 填到 GitHub Secret 的 `CHAT_NOTIFY_HUB_URL`,還有本機 `.env`

**選 B. 你自己的 chat-notify-hub**
1. 把 `chat-notify-hub` 部署到可公開存取的 endpoint(例如 ngrok、Vercel、Railway)
2. URL 填到 secret,系統發 `POST <url>` 帶 `{type, severity, payload}` JSON

**選 C. 先不接**:`CHAT_NOTIFY_HUB_URL` 留空,系統照跑,只是沒通知。事後用 `python -m scripts.status` 看狀態(見下節)。

## 4. Push 本機 repo 上 GitHub

1. https://github.com/new 建 **private** repo,名稱 `crypto-ai-agent`,**不要**勾 init README/.gitignore
2. 本機:
   ```bash
   cd C:\Projects\crypto-ai-agent
   git remote add origin https://github.com/<your-username>/crypto-ai-agent.git
   git push -u origin master
   ```

## 5. 設 GitHub Secrets

Repo → Settings → Secrets and variables → Actions → New repository secret,新增 5 個:

| Name | Value |
|---|---|
| `TURSO_DB_URL` | (步驟 1.4 的 URL) |
| `TURSO_AUTH_TOKEN` | (步驟 1.4 的 JWT) |
| `BINANCE_API_KEY` | (步驟 2.2 的 key) |
| `BINANCE_API_SECRET` | (步驟 2.2 的 secret) |
| `CHAT_NOTIFY_HUB_URL` | (步驟 3 的 endpoint URL) |

## 6. 本機 .env

```bash
cd C:\Projects\crypto-ai-agent
cp .env.example .env
```

編輯 `.env`,填入跟 GitHub Secrets 一樣的值(`.env` 不會 commit,在 .gitignore 內)。

## 7. 第一次跑 migrate(把 schema 推到 Turso)

從 GitHub Actions UI:

1. Repo → Actions → `exec_manual` → Run workflow
2. Action 選 `migrate`,Run
3. 30 秒後看到 green check;log 裡會印 `Applied versions: [1, 2]`

或本機跑(產出一樣):

```bash
source venv/Scripts/activate
python -m scripts.migrate_turso
```

## 8. 注入第一筆 signal

GitHub Actions UI:

1. Repo → Actions → `exec_manual` → Run workflow
2. Action 選 `seed`,Symbol 留 `BTCUSDT`,Size 留 `50`,Run
3. log 裡會印 `Inserted signal: id=1 ...`

或本機:

```bash
python -m scripts.seed_signal --symbol BTCUSDT --size 50
```

## 9. 等 5 分鐘看自動 tick 跑(或手動觸發)

選一個:

- **等**:cron 每 5 分鐘觸發一次 `exec_tick`,你會在 Actions 頁看到自動跑的 workflow
- **手動**:Actions → `exec_tick` → Run workflow,30 秒見效

Workflow 跑完後檢查(最方便的方式):

```bash
cd C:\Projects\crypto-ai-agent && source venv/Scripts/activate
python -m scripts.status
```

會看到 positions、recent orders、recent events、Binance 餘額,一頁全看完。

Discord 也應該收到 `[INFO] fill` 卡片(如果你選了 Discord webhook)。

(注意:testnet.binance.vision 沒有傳統的 dashboard UI,主要靠 API。我們的 `status.py` 就是替代品。)

## 9b. status CLI(P1.5 新增)

任何時候想看當前狀態:

```bash
python -m scripts.status                # 一次性
python -m scripts.status --watch        # 每 10 秒自動 refresh
python -m scripts.status --no-exchange  # 跳過 Binance API(離線或想看快點)
```

印出:positions / signals / orders / events / control flags / Binance balances / open orders。

## 10. 接下來:讓它跑 3 天

P1 的 exit criteria:**連續 3 天 cron 跑無 critical error**。所以接下來什麼都不用做,讓系統自己跑。

每天早上花 1 分鐘看:

- Actions 頁 cron 都成功(綠 check)
- Discord 沒有 `[ERROR]` 卡片(或 chat-notify-hub `severity=error` 訊息)
- `python -m scripts.status` 看 positions / orders 沒爆,event log 沒一堆 error

3 天後 → P2 開工(把 Cowork-side 真實策略推理接進來,取代 manual seed)。

## 緊急停止

如果發現有問題要停掉:

1. Repo → Actions → `exec_tick` → 右上 "..." → "Disable workflow"
2. 或在 Turso 改 kill_switch:
   ```bash
   turso db shell crypto-ai-agent "UPDATE control SET value='true' WHERE key='kill_switch';"
   ```
3. 第二招更徹底:把 GHA workflow 停掉,雲端就不會再跑

## 疑難排解

| 症狀 | 可能原因 | 解法 |
|---|---|---|
| GHA workflow 紅了,log 顯示 `RuntimeError: libsql error: SQLITE_AUTH` | TURSO_AUTH_TOKEN 過期 / 錯了 | 重新建 token、更新 secret |
| 紅,`binance.exceptions.BinanceAPIException: Invalid API-key` | API key 沒給 testnet 權限 | 檢查 testnet.binance.vision,重新 generate |
| 跑成功但 testnet 帳戶沒成交 | 你 seed 的 symbol 不在 strategy 的 universe 裡 | seed 時不要改 symbol,用 BTCUSDT/ETHUSDT/SOLUSDT |
| Discord 沒收到通知 | CHAT_NOTIFY_HUB_URL 沒設,或 chat-notify-hub 沒在跑 | 檢查 secret,或先用任意 webhook URL 試 |
| `pip install` 卡在 libsql-experimental | 你裝到舊版需求檔了 | 確認 requirements.txt 沒有 libsql-experimental(我們用 HTTP API,不用編譯) |
