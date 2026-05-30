# crypto-ai-agent P1 (Cloud Deploy) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 P0 跑通的本機骨架搬上雲端。Turso 取代本機 SQLite、Binance testnet adapter 真的下單、GitHub Actions cron 每 5 分鐘自動跑 tick、Discord 收得到事件通知。完工後使用者只要本機跑一次 `seed_signal.py` 注入一筆 signal,即可在 Binance testnet 看到實際成交,後續 GHA 24/7 自動運作。

**Architecture:** db/client.py 加 libsql:// scheme(libsql_client SDK,參數同 sqlite3),adapter 層新增 binance.py(python-binance testnet)與 notify/(chat-notify-hub HTTP POST adapter)。tick.py 注入 notifier 依賴,在 fill / error / kill_switch 事件呼叫。GHA workflow 兩支:`exec_tick.yml`(cron 5 分鐘)、`exec_manual.yml`(workflow_dispatch)。Cowork 端真實 pipeline 留給 P2;P1 用 `scripts/seed_signal.py` 手動注入測試 signal。

**Tech Stack:** Python 3.11+、libsql-experimental(Turso 連線)、python-binance(交易所)、requests(notify HTTP)、GitHub Actions(cron)、pytest 既有設定不變。

---

## 重要紀律(每個 task 都要遵守)

繼承 P0 的同 6 條(stock CLAUDE.md):
1. 改 .py 後跑測試前 `touch <file>`(Windows 掛載目錄 .pyc 殘留風險)
2. .bat 純 ASCII,首行 `chcp 65001 > nul`
3. 長檔走 heredoc(>100 行 Python/markdown)
4. 四連驗證:`wc -l` + `tail -5`、`python -c import`、`compileall`、跑該 task pytest

## P1 不做的(留給 P2/P3)

- `pipeline/` Cowork 端策略推理(P2)
- `bridge/` 三支腳本(P2,因為 Cowork 還沒寫檔給 bridge 同步)
- `_START_HERE/*.bat` 控制台(P3)
- `daily_report` cron + reporter.py(P3)
- Stop-loss / take-profit 觸發邏輯(P2)
- 多 strategy / 多交易所(後續)

## 整體流程

| Task | 主題 | 約時 |
|---|---|---|
| **0** | 使用者外部準備工作(checklist,user action)| user 30 min |
| 1 | 升級 requirements.txt(加 libsql-experimental / python-binance / requests / responses)| 5 min |
| 2 | Notifier Protocol + FakeNotifier | 15 min |
| 3 | chat-notify-hub HTTP adapter | 20 min |
| 4 | Wire notifier into tick.py | 25 min |
| 5 | db/client.py 加 libsql:// scheme | 25 min |
| 6 | scripts/migrate_turso.py(一次性遷移腳本)| 15 min |
| 7 | Binance adapter(python-binance wrapping)| 40 min |
| 8 | scripts/seed_signal.py CLI | 20 min |
| 9 | .github/workflows/exec_tick.yml(cron)| 30 min |
| 10 | .github/workflows/exec_manual.yml(workflow_dispatch)| 15 min |
| 11 | docs/P1_SETUP.md(使用者操作說明)| 20 min |
| 12 | End-to-end testnet smoke(manual checklist)| 40 min |

**約 5–6 小時 + 使用者外部準備 30 min ≈ 半天到一天能跑完 P1。**

---

## File Structure(P1 結束時)

```
C:\Projects\crypto-ai-agent\
├── .github\
│   └── workflows\
│       ├── exec_tick.yml             (P1 新增,cron */5 * * * *)
│       └── exec_manual.yml           (P1 新增,workflow_dispatch)
├── adapters\
│   ├── exchanges\
│   │   ├── base.py                   (P0,不動)
│   │   ├── _fake.py                  (P0,不動)
│   │   └── binance.py                (P1 新增)
│   └── notify\                       (P1 新增 dir)
│       ├── __init__.py
│       ├── base.py                   (Notifier Protocol + FakeNotifier)
│       └── chat_notify_hub.py        (HTTP POST adapter)
├── db\
│   └── client.py                     (P1 修改:加 libsql:// scheme + auth_token kwarg)
├── executor\
│   └── tick.py                       (P1 修改:注入 notifier、emit 事件)
├── scripts\                          (P1 新增 dir)
│   ├── __init__.py
│   ├── migrate_turso.py              一次性遷移 schema 到 Turso
│   └── seed_signal.py                CLI 注入測試 signal 到 Turso
├── docs\
│   └── P1_SETUP.md                   (P1 新增,使用者外部準備說明)
├── tests\
│   ├── test_notify_base.py           (P1 新增)
│   ├── test_notify_chat_hub.py       (P1 新增)
│   ├── test_db_libsql.py             (P1 新增,parsing only)
│   ├── test_binance.py               (P1 新增,mocked)
│   └── test_tick_notify.py           (P1 新增)
└── requirements.txt                  (P1 修改:加 4 個 deps)
```

---

## Task 0: 使用者外部準備工作(必須先做完才能跑 Task 7+)

**這個 Task 不是程式工作,是使用者操作清單**。subagent 跑到 Task 7+ 之前,使用者必須完成下列項目並把產物(URL / token / API key)記下來。

- [ ] **0.1 申請 Turso 帳號 + 建 DB**
  1. 開 https://turso.tech,Sign up(可用 GitHub 登入)
  2. CLI 安裝(可選):`curl -sSfL https://get.tur.so/install.sh | bash` 然後 `turso auth login`(也可用 web UI 完全做完)
  3. 建一個 DB,例如 `crypto-ai-agent`:
     - Web UI:Databases → Create database → Name=`crypto-ai-agent`,Region 選最近的(東京 nrt 或新加坡 sin)
     - CLI:`turso db create crypto-ai-agent --location nrt`
  4. 取得連線 URL:`turso db show crypto-ai-agent --url`(格式 `libsql://crypto-ai-agent-<username>.turso.io`)
  5. 建 auth token:`turso db tokens create crypto-ai-agent`(輸出一長串 JWT)
  6. **把兩者記下來**:`TURSO_DB_URL` 和 `TURSO_AUTH_TOKEN`

- [ ] **0.2 申請 Binance testnet API key**
  1. 開 https://testnet.binance.vision/
  2. 用 GitHub 登入(或建立 testnet 帳號)
  3. Generate HMAC_SHA256 Key → 取得 `BINANCE_API_KEY` 和 `BINANCE_API_SECRET`
  4. 餘額:testnet 預設給你一些假錢(BTC、USDT 等),不夠就點 Faucet
  5. **把兩個 secret 記下來**

- [ ] **0.3 把本機 repo push 到 GitHub**
  1. 開 https://github.com/new 建一個 **private** repo,名稱 `crypto-ai-agent`(不要 init README,我們本地已經有)
  2. 本機:
     ```bash
     cd /c/Projects/crypto-ai-agent
     git remote add origin https://github.com/<your-username>/crypto-ai-agent.git
     git push -u origin master
     ```
  3. 確認 GitHub repo 看得到所有 P0 commits

- [ ] **0.4 在 GitHub repo 設 Secrets**
  Settings → Secrets and variables → Actions → New repository secret,新增 5 個:
  | Secret name | Value |
  |---|---|
  | `TURSO_DB_URL` | (Task 0.1 的 URL) |
  | `TURSO_AUTH_TOKEN` | (Task 0.1 的 JWT) |
  | `BINANCE_API_KEY` | (Task 0.2 的 key) |
  | `BINANCE_API_SECRET` | (Task 0.2 的 secret) |
  | `CHAT_NOTIFY_HUB_URL` | (你 chat-notify-hub 的 webhook endpoint URL;如果還沒架好,先用任意 Discord webhook URL 替代,GHA 失敗時你會收到通知) |

- [ ] **0.5 在本機 `.env` 也設一份(本機跑 scripts 用)**
  ```bash
  cd /c/Projects/crypto-ai-agent
  cp .env.example .env
  # 編輯 .env,填入 0.1–0.4 的值
  ```
  `.env` 已在 `.gitignore` 內,不會 commit。

**完成 0.1–0.5 後才能繼續 Task 7+。Task 1–6 不需要外部資源,可以先做。**

---

## Task 1: 升級 requirements.txt

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1.1: 編輯 requirements.txt**

新增 4 行(在現有 3 行下面):

```
pytest==8.3.3
pytest-cov==5.0.0
python-dateutil==2.9.0
libsql-experimental==0.0.41
python-binance==1.0.24
requests==2.32.3
responses==0.25.7
```

- [ ] **Step 1.2: 重新裝**

```bash
cd /c/Projects/crypto-ai-agent && source venv/Scripts/activate
pip install -r requirements.txt
python -c "import libsql_experimental, binance, requests, responses; print('OK')"
```

Expected: `OK`

- [ ] **Step 1.3: 跑現有測試確保沒打壞**

```bash
pytest tests/ --tb=short -q
```

Expected: 67 passed.

- [ ] **Step 1.4: Commit**

```bash
git add requirements.txt
git -c user.email=yihuang0903@gmail.com -c user.name=riverkid commit -m "build(p1): add libsql-experimental / python-binance / requests / responses

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: Notifier Protocol + FakeNotifier

**Files:**
- Create: `adapters/notify/__init__.py` (empty)
- Create: `adapters/notify/base.py`
- Create: `tests/test_notify_base.py`

- [ ] **Step 2.1: 寫 tests/test_notify_base.py**

```python
from adapters.notify.base import FakeNotifier, Notification


def test_fake_notifier_records_messages():
    n = FakeNotifier()
    n.send(Notification(type="fill", severity="info", payload={"symbol": "BTC", "qty": 0.01}))
    assert len(n.sent) == 1
    assert n.sent[0].type == "fill"
    assert n.sent[0].severity == "info"
    assert n.sent[0].payload["symbol"] == "BTC"


def test_fake_notifier_records_multiple_messages():
    n = FakeNotifier()
    n.send(Notification(type="fill", severity="info", payload={"symbol": "BTC"}))
    n.send(Notification(type="error", severity="error", payload={"err": "timeout"}))
    types = [m.type for m in n.sent]
    assert types == ["fill", "error"]


def test_fake_notifier_can_simulate_failure():
    n = FakeNotifier(fail=True)
    # send returns False on failure, doesn't raise
    ok = n.send(Notification(type="fill", severity="info", payload={}))
    assert ok is False
    # message still recorded in attempts
    assert len(n.sent) == 1


def test_fake_notifier_success_default():
    n = FakeNotifier()
    ok = n.send(Notification(type="fill", severity="info", payload={}))
    assert ok is True
```

- [ ] **Step 2.2: 跑測試確認 fail**

```bash
pytest tests/test_notify_base.py -v
```

Expected: ImportError for `adapters.notify.base`

- [ ] **Step 2.3: 建 adapters/notify/__init__.py(空檔)**

```bash
touch adapters/notify/__init__.py
```

- [ ] **Step 2.4: 寫 adapters/notify/base.py**

```python
"""Notifier abstraction (Protocol + in-memory fake for tests)."""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Protocol


@dataclass
class Notification:
    type: str                   # e.g. "fill" / "error" / "kill_switch" / "blocked"
    severity: str               # "info" / "warn" / "error"
    payload: Dict[str, Any]


class Notifier(Protocol):
    def send(self, notification: Notification) -> bool:
        """Send a notification. Return True on success, False on failure.

        Implementations must NOT raise on transport errors — return False instead,
        so the tick loop can continue even if Discord/webhook is down.
        """


class FakeNotifier:
    """In-memory notifier for tests. Records all attempts."""

    def __init__(self, fail: bool = False):
        self._fail = fail
        self.sent: List[Notification] = []

    def send(self, notification: Notification) -> bool:
        self.sent.append(notification)
        return not self._fail
```

- [ ] **Step 2.5: 跑測試確認 pass**

```bash
pytest tests/test_notify_base.py -v
```

Expected: 4 passed.

- [ ] **Step 2.6: Commit**

```bash
git add adapters/notify/__init__.py adapters/notify/base.py tests/test_notify_base.py
git -c user.email=yihuang0903@gmail.com -c user.name=riverkid commit -m "feat(p1): add Notifier Protocol + FakeNotifier

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: chat-notify-hub HTTP Adapter

**Files:**
- Create: `adapters/notify/chat_notify_hub.py`
- Create: `tests/test_notify_chat_hub.py`

設計:`ChatNotifyHubNotifier(url, timeout=5)` POST JSON 到 chat-notify-hub URL。payload 格式我們先約定:
```json
{
  "type": "fill",
  "severity": "info",
  "payload": {"symbol": "BTC", "qty": 0.01, "price": 60000}
}
```
chat-notify-hub 端怎麼解析、轉發到 Discord/Telegram,是 chat-notify-hub 自己的事(它本來就是這個職責)。我們只負責把訊息丟出去。

測試用 `responses` library mock HTTP,不打真網路。

- [ ] **Step 3.1: 寫 tests/test_notify_chat_hub.py**

```python
import responses
from adapters.notify.base import Notification
from adapters.notify.chat_notify_hub import ChatNotifyHubNotifier


HUB_URL = "http://localhost:9001/notify"


@responses.activate
def test_send_posts_json_and_returns_true_on_200():
    responses.add(responses.POST, HUB_URL, json={"ok": True}, status=200)
    notifier = ChatNotifyHubNotifier(HUB_URL)
    ok = notifier.send(Notification(
        type="fill", severity="info",
        payload={"symbol": "BTC", "qty": 0.01},
    ))
    assert ok is True
    assert len(responses.calls) == 1
    body = responses.calls[0].request.body
    import json
    parsed = json.loads(body)
    assert parsed["type"] == "fill"
    assert parsed["severity"] == "info"
    assert parsed["payload"]["symbol"] == "BTC"


@responses.activate
def test_send_returns_false_on_5xx():
    responses.add(responses.POST, HUB_URL, status=500)
    notifier = ChatNotifyHubNotifier(HUB_URL)
    ok = notifier.send(Notification(type="error", severity="error", payload={}))
    assert ok is False


@responses.activate
def test_send_returns_false_on_connection_error():
    responses.add(responses.POST, HUB_URL, body=ConnectionError("boom"))
    notifier = ChatNotifyHubNotifier(HUB_URL)
    ok = notifier.send(Notification(type="error", severity="error", payload={}))
    # Must NOT raise — must return False
    assert ok is False


@responses.activate
def test_send_respects_timeout_kwarg():
    responses.add(responses.POST, HUB_URL, json={"ok": True}, status=200)
    notifier = ChatNotifyHubNotifier(HUB_URL, timeout=10)
    notifier.send(Notification(type="fill", severity="info", payload={}))
    # responses library doesn't expose timeout to assert, but request must complete
    assert len(responses.calls) == 1
```

- [ ] **Step 3.2: 跑測試確認 fail**

```bash
pytest tests/test_notify_chat_hub.py -v
```

Expected: ImportError for `adapters.notify.chat_notify_hub`

- [ ] **Step 3.3: 寫 adapters/notify/chat_notify_hub.py**

```python
"""HTTP POST adapter that pushes to chat-notify-hub."""
import json
import requests
from adapters.notify.base import Notification


class ChatNotifyHubNotifier:
    def __init__(self, url: str, timeout: float = 5.0):
        self._url = url
        self._timeout = timeout

    def send(self, notification: Notification) -> bool:
        body = {
            "type": notification.type,
            "severity": notification.severity,
            "payload": notification.payload,
        }
        try:
            resp = requests.post(
                self._url,
                data=json.dumps(body),
                headers={"Content-Type": "application/json"},
                timeout=self._timeout,
            )
            return 200 <= resp.status_code < 300
        except requests.exceptions.RequestException:
            return False
        except ConnectionError:
            return False
```

- [ ] **Step 3.4: 跑測試**

```bash
pytest tests/test_notify_chat_hub.py -v
```

Expected: 4 passed.

- [ ] **Step 3.5: Commit**

```bash
git add adapters/notify/chat_notify_hub.py tests/test_notify_chat_hub.py
git -c user.email=yihuang0903@gmail.com -c user.name=riverkid commit -m "feat(p1): add ChatNotifyHubNotifier (HTTP POST + safe failures)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: Wire Notifier into tick.py

**Files:**
- Modify: `executor/tick.py`
- Create: `tests/test_tick_notify.py`

設計:
- `run_tick(db, exchange, notifier=None, strategy_name="trend_majors")` — 加 optional notifier 參數
- 在 5 個事件點呼叫 notifier.send():
  - `fill`(severity=info):成功成交
  - `blocked`(severity=info):被 circuit breaker 擋
  - `error`(severity=error):API 失敗
  - `kill_switch`(severity=error):kill switch 自動觸發(目前在 circuit_breaker 內,需要 tick 監看 control 狀態變化)
  - `circuit_open`(severity=warn):per-symbol 熔斷

實作策略:不直接在 tick.py 五個地方插 notifier.send,而是「讀 events log 後 forward」。每 tick 結束時,挑當 tick 新增的 events 中該推送的類型,推到 notifier。優點:單一進入點、容易測試。

- [ ] **Step 4.1: 寫 tests/test_tick_notify.py**

```python
from datetime import datetime, timedelta, timezone
import pytest
from adapters.exchanges._fake import FakeExchange
from adapters.notify.base import FakeNotifier
from db.repos.signals import Signals
from db.repos.strategies import Strategies
from executor.tick import run_tick


def _future_iso(hours=24):
    return (datetime.now(timezone.utc) + timedelta(hours=hours)).isoformat()


def _setup_strategy(db, universe):
    Strategies(db).insert(name="trend_majors", params={"universe": universe})


def test_fill_emits_info_notification(db):
    _setup_strategy(db, universe=["BTCUSDT"])
    Signals(db).insert(
        strategy_id=1, symbol="BTCUSDT", side="long",
        entry_price=None, stop_price=None, target_price=None,
        size_usdt=100.0, expires_at=_future_iso(), reason="",
    )
    ex = FakeExchange()
    ex.set_price("BTCUSDT", 60000.0)
    notifier = FakeNotifier()
    run_tick(db, ex, notifier=notifier, strategy_name="trend_majors")
    fills = [n for n in notifier.sent if n.type == "fill"]
    assert len(fills) == 1
    assert fills[0].severity == "info"
    assert fills[0].payload["symbol"] == "BTCUSDT"


def test_blocked_emits_info_notification(db):
    _setup_strategy(db, universe=["BTCUSDT"])
    Signals(db).insert(
        strategy_id=1, symbol="DOGEUSDT", side="long",
        entry_price=None, stop_price=None, target_price=None,
        size_usdt=100.0, expires_at=_future_iso(), reason="",
    )
    ex = FakeExchange()
    notifier = FakeNotifier()
    run_tick(db, ex, notifier=notifier, strategy_name="trend_majors")
    blocked = [n for n in notifier.sent if n.type == "blocked"]
    assert len(blocked) == 1
    assert blocked[0].severity == "info"


def test_error_emits_error_notification(db):
    _setup_strategy(db, universe=["BTC"])
    Signals(db).insert(
        strategy_id=1, symbol="BTC", side="long",
        entry_price=None, stop_price=None, target_price=None,
        size_usdt=100.0, expires_at=_future_iso(), reason="",
    )
    ex = FakeExchange()
    ex.set_price("BTC", 60000.0)
    ex.fail_next_n_orders(1)
    notifier = FakeNotifier()
    run_tick(db, ex, notifier=notifier, strategy_name="trend_majors")
    errors = [n for n in notifier.sent if n.type == "error"]
    assert len(errors) == 1
    assert errors[0].severity == "error"


def test_no_notifier_doesnt_break(db):
    """tick.py without notifier should still work (None default)."""
    _setup_strategy(db, universe=["BTCUSDT"])
    Signals(db).insert(
        strategy_id=1, symbol="BTCUSDT", side="long",
        entry_price=None, stop_price=None, target_price=None,
        size_usdt=100.0, expires_at=_future_iso(), reason="",
    )
    ex = FakeExchange()
    ex.set_price("BTCUSDT", 60000.0)
    summary = run_tick(db, ex, strategy_name="trend_majors")  # no notifier
    assert summary["triggered"] == 1


def test_notifier_failure_doesnt_break_tick(db):
    """If notifier.send fails, tick still completes successfully."""
    _setup_strategy(db, universe=["BTCUSDT"])
    Signals(db).insert(
        strategy_id=1, symbol="BTCUSDT", side="long",
        entry_price=None, stop_price=None, target_price=None,
        size_usdt=100.0, expires_at=_future_iso(), reason="",
    )
    ex = FakeExchange()
    ex.set_price("BTCUSDT", 60000.0)
    notifier = FakeNotifier(fail=True)
    summary = run_tick(db, ex, notifier=notifier, strategy_name="trend_majors")
    # The fill still happened
    assert summary["triggered"] == 1
    # Notifier was attempted
    assert len(notifier.sent) >= 1
```

- [ ] **Step 4.2: 跑測試確認 fail**

```bash
pytest tests/test_tick_notify.py -v
```

Expected: 5 個 ImportError 或 AssertionError(notifier 還沒接)

- [ ] **Step 4.3: 修改 executor/tick.py**

修改 signature 加 `notifier` 參數,並在 events 寫入後 forward 到 notifier。

完整新版 tick.py(替換整個 run_tick 函式,以及增加一個 helper):

替換 run_tick 函式為:

```python
def run_tick(db: Database, exchange: Exchange,
             notifier=None,
             strategy_name: str = "trend_majors") -> dict:
    strategies = Strategies(db)
    signals = Signals(db)
    orders = Orders(db)
    positions = Positions(db)
    events = Events(db)
    cb = CircuitBreaker(Control(db), positions, events)

    strategy = strategies.get_by_name(strategy_name)
    if strategy is None:
        events.log("error", {"msg": f"strategy not found: {strategy_name}"})
        _notify_safe(notifier, "error", "error",
                     {"msg": f"strategy not found: {strategy_name}"})
        return {"triggered": 0, "blocked": 0, "api_errors": 0}

    universe = strategy.params.get("universe", [])
    summary = {"triggered": 0, "blocked": 0, "api_errors": 0}

    for sig in signals.list_active():
        # 0. universe pre-check
        if sig.symbol not in universe:
            payload = {
                "signal_id": sig.id, "symbol": sig.symbol,
                "reason": f"universe: {sig.symbol} not in whitelist",
            }
            events.log("blocked", payload)
            _notify_safe(notifier, "blocked", "info", payload)
            summary["blocked"] += 1
            continue

        # 0b. per-symbol API circuit
        if cb.should_circuit_open(sig.symbol):
            payload = {
                "signal_id": sig.id, "symbol": sig.symbol,
                "reason": f"circuit_open: api failures for {sig.symbol} >= threshold",
            }
            events.log("blocked", payload)
            _notify_safe(notifier, "blocked", "info", payload)
            summary["blocked"] += 1
            continue

        # 1. get current price
        try:
            current_price = exchange.get_price(sig.symbol)
        except Exception as exc:
            cb.note_api_failure(sig.symbol)
            payload = {"phase": "get_price", "symbol": sig.symbol, "err": str(exc)}
            events.log("error", payload)
            _notify_safe(notifier, "error", "error", payload)
            summary["api_errors"] += 1
            continue

        # 2. matcher
        holding = positions.get_qty(sig.symbol)
        if not should_trigger(sig, current_price, holding_qty=holding):
            continue

        # 3. circuit breaker (P0: daily_realized_pnl=0)
        reason = cb.evaluate_new_entry(
            symbol=sig.symbol, size_usdt=sig.size_usdt,
            universe=universe, daily_realized_pnl=0.0,
        )
        if reason is not None:
            payload = {
                "signal_id": sig.id, "symbol": sig.symbol, "reason": reason,
            }
            events.log("blocked", payload)
            _notify_safe(notifier, "blocked", "info", payload)
            # Special: if reason contains kill_switch, also emit kill_switch notice
            if "kill_switch" in reason.lower() or "daily_loss" in reason.lower():
                _notify_safe(notifier, "kill_switch", "error", payload)
            summary["blocked"] += 1
            continue

        # 4. place order (market only in P0)
        qty = sig.size_usdt / current_price
        order_id = orders.insert(
            signal_id=sig.id, exchange_order_id=None,
            symbol=sig.symbol, side="buy", qty=qty,
            price=None, type="market", status="new",
        )
        try:
            ex_order = exchange.place_order(sig.symbol, "buy", qty, type="market")
        except Exception as exc:
            cb.note_api_failure(sig.symbol)
            payload = {"phase": "place_order", "symbol": sig.symbol, "err": str(exc)}
            events.log("error", payload)
            _notify_safe(notifier, "error", "error", payload)
            orders.mark_failed(order_id)
            summary["api_errors"] += 1
            continue

        if ex_order.status != "filled":
            cb.note_api_failure(sig.symbol)
            payload = {"phase": "fill", "symbol": sig.symbol, "status": ex_order.status}
            events.log("error", payload)
            _notify_safe(notifier, "error", "error", payload)
            orders.mark_failed(order_id)
            summary["api_errors"] += 1
            continue

        # 5. write back state
        orders.update_fill(
            order_id, fill_qty=ex_order.fill_qty,
            fill_price=ex_order.fill_price, fee_usdt=ex_order.fee_usdt,
            status="filled",
        )
        positions.upsert(sig.symbol, qty=ex_order.fill_qty,
                         avg_entry=ex_order.fill_price, current_price=current_price)
        signals.mark_triggered(sig.id)
        cb.note_api_success(sig.symbol)
        payload = {
            "signal_id": sig.id, "symbol": sig.symbol,
            "qty": ex_order.fill_qty, "price": ex_order.fill_price,
            "fee_usdt": ex_order.fee_usdt,
        }
        events.log("fill", payload)
        _notify_safe(notifier, "fill", "info", payload)
        summary["triggered"] += 1

    return summary


def _notify_safe(notifier, type: str, severity: str, payload: dict) -> None:
    """Best-effort notify. Swallow all exceptions — the tick must complete."""
    if notifier is None:
        return
    try:
        from adapters.notify.base import Notification
        notifier.send(Notification(type=type, severity=severity, payload=payload))
    except Exception:
        # Even if notifier raises (shouldn't, per spec), don't break the tick
        pass
```

Also update `main()` to inject a real notifier when `CHAT_NOTIFY_HUB_URL` env is set:

替換 main() 函式為:

```python
def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fake", action="store_true",
                        help="use FakeExchange + in-memory data for smoke test")
    parser.add_argument("--strategy", default="trend_majors")
    args = parser.parse_args()

    # Notifier from env (always optional)
    notifier = None
    hub_url = os.environ.get("CHAT_NOTIFY_HUB_URL", "").strip()
    if hub_url:
        from adapters.notify.chat_notify_hub import ChatNotifyHubNotifier
        notifier = ChatNotifyHubNotifier(hub_url)

    if args.fake:
        db = Database(":memory:")
        migrate(db)
        Strategies(db).insert(name="trend_majors",
                              params={"universe": ["BTCUSDT", "ETHUSDT", "SOLUSDT"]})
        from datetime import datetime, timedelta, timezone
        expires = (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat()
        Signals(db).insert(
            strategy_id=1, symbol="BTCUSDT", side="long",
            entry_price=None, stop_price=58000.0, target_price=65000.0,
            size_usdt=300.0, expires_at=expires, reason="fake smoke signal",
        )
        ex = FakeExchange()
        ex.set_price("BTCUSDT", 60000.0)
        ex.set_price("ETHUSDT", 3000.0)
        ex.set_price("SOLUSDT", 150.0)
        summary = run_tick(db, ex, notifier=notifier, strategy_name=args.strategy)
        print(f"[fake tick] summary: {summary}")
        for pos in Positions(db).list_all():
            print(f"  position: {pos.symbol} qty={pos.qty:.6f} avg_entry={pos.avg_entry}")
        return 0

    # Non-fake mode requires Binance adapter — added in Task 7
    db_url = os.environ.get("DB_URL", "sqlite:///state/local.db")
    with Database(db_url) as db:
        from adapters.exchanges.binance import BinanceExchange
        ex = BinanceExchange(
            api_key=os.environ.get("BINANCE_API_KEY", ""),
            api_secret=os.environ.get("BINANCE_API_SECRET", ""),
            testnet=os.environ.get("BINANCE_TESTNET", "true").lower() == "true",
        )
        summary = run_tick(db, ex, notifier=notifier, strategy_name=args.strategy)
        print(f"[live tick] summary: {summary}")
        return 0
```

**注意**:`from adapters.exchanges.binance import BinanceExchange` 是在 main() 內 deferred import,因為 Task 7 才會建這個檔。這個 import 不會在 Task 4 的測試裡被觸發(`--fake` mode 走另一條路徑)。如果不放心,Task 4 可以在 main() 內把那段註解掉,Task 7 完成時再打開。

- [ ] **Step 4.4: 跑測試**

```bash
pytest tests/test_tick_notify.py tests/test_tick.py tests/test_tick_e2e.py tests/ -v --tb=short -q
```

Expected: 全綠(67 + 5 = 72 passed)。

- [ ] **Step 4.5: CLI smoke 沒壞**

```bash
python -m executor.tick --fake
```

Expected: 跟 P0 結束一樣的輸出:
```
[fake tick] summary: {'triggered': 1, 'blocked': 0, 'api_errors': 0}
  position: BTCUSDT qty=0.005000 avg_entry=60000.0
```

- [ ] **Step 4.6: Commit**

```bash
git add executor/tick.py tests/test_tick_notify.py
git -c user.email=yihuang0903@gmail.com -c user.name=riverkid commit -m "feat(p1): wire optional notifier into tick (fill/blocked/error/kill_switch)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: db/client.py 加 libsql:// scheme

**Files:**
- Modify: `db/client.py`
- Create: `tests/test_db_libsql.py`(parsing 測試only,不打真 Turso)

設計:
- `Database(url, auth_token=None)` — 加 auth_token kwarg
- `_parse(url)` 不再回傳 path,改回傳 `(scheme, target, auth_token)`
- sqlite scheme:scheme="sqlite",target=path,auth_token=None
- libsql scheme:scheme="libsql",target=full URL,auth_token=arg
- `__init__` 根據 scheme 用不同的 connect 函式

具體實作策略:libsql_experimental 的 API 跟 sqlite3 高度相似(execute / fetchall / commit / close),可以保留 Database 的對外 API 不變。

- [ ] **Step 5.1: 寫 tests/test_db_libsql.py(只測 parsing,不打真 Turso)**

```python
import pytest
from db.client import Database, _parse_url


def test_parse_memory():
    scheme, target, token = _parse_url(":memory:", auth_token=None)
    assert scheme == "sqlite"
    assert target == ":memory:"
    assert token is None


def test_parse_sqlite_file():
    scheme, target, token = _parse_url("sqlite:///state/local.db", auth_token=None)
    assert scheme == "sqlite"
    assert target == "state/local.db"
    assert token is None


def test_parse_libsql_with_token():
    url = "libsql://my-db-username.turso.io"
    scheme, target, token = _parse_url(url, auth_token="jwt-token-here")
    assert scheme == "libsql"
    assert target == url
    assert token == "jwt-token-here"


def test_parse_libsql_without_token_raises():
    with pytest.raises(ValueError, match="libsql.*auth_token"):
        _parse_url("libsql://my-db.turso.io", auth_token=None)


def test_parse_unknown_scheme_raises():
    with pytest.raises(ValueError, match="unsupported"):
        _parse_url("postgres://x", auth_token=None)


# Existing P0 tests still hold (memory / file work)
def test_memory_db_still_works():
    db = Database(":memory:")
    db.execute("CREATE TABLE t (id INT)")
    db.execute("INSERT INTO t VALUES (1)")
    assert db.query("SELECT * FROM t") == [(1,)]
    db.close()
```

- [ ] **Step 5.2: 跑測試確認 fail**

```bash
pytest tests/test_db_libsql.py -v
```

Expected: ImportError for `_parse_url`(它原本是 staticmethod `Database._parse`,現在我們要 expose 成 module-level helper)

- [ ] **Step 5.3: 修改 db/client.py**

替換整個檔案:

```python
"""Thin wrapper over sqlite3 / libsql with a connection-string API.

Supported schemes:
- ":memory:"             — in-memory sqlite (tests)
- "sqlite:///path/to.db" — local file sqlite
- "libsql://<host>"      — Turso cloud (requires auth_token kwarg)
"""
import sqlite3
from pathlib import Path
from typing import Any, Iterable, List, Optional, Tuple


def _parse_url(url: str, auth_token: Optional[str] = None) -> Tuple[str, str, Optional[str]]:
    """Return (scheme, target, auth_token).

    scheme: "sqlite" or "libsql"
    target: path string for sqlite, full URL for libsql
    auth_token: passed through unchanged for libsql; ignored for sqlite
    """
    if url == ":memory:":
        return ("sqlite", ":memory:", None)
    if url.startswith("sqlite:///"):
        return ("sqlite", url[len("sqlite:///"):], None)
    if url.startswith("sqlite://"):
        return ("sqlite", url[len("sqlite://"):], None)
    if url.startswith("libsql://"):
        if not auth_token:
            raise ValueError(f"libsql requires auth_token (DB url: {url})")
        return ("libsql", url, auth_token)
    raise ValueError(f"unsupported DB url: {url}")


class Database:
    def __init__(self, url: str, auth_token: Optional[str] = None):
        scheme, target, token = _parse_url(url, auth_token)
        if scheme == "sqlite":
            if target != ":memory:":
                Path(target).parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(target)
            self._conn.execute("PRAGMA foreign_keys = ON")
        else:  # libsql
            import libsql_experimental as libsql
            self._conn = libsql.connect(target, auth_token=token)
            # libsql_experimental doesn't support PRAGMA via execute the same way,
            # foreign key behavior is enabled by default for Turso.

    def execute(self, sql: str, params: Iterable[Any] = ()) -> int:
        cur = self._conn.execute(sql, tuple(params))
        self._conn.commit()
        return cur.lastrowid

    def executescript(self, script: str) -> None:
        # libsql_experimental doesn't have executescript directly; split + execute
        if hasattr(self._conn, "executescript"):
            self._conn.executescript(script)
        else:
            # Split on semicolons, skip empty
            for stmt in script.split(";"):
                stmt = stmt.strip()
                if stmt:
                    self._conn.execute(stmt)
        self._conn.commit()

    def query(self, sql: str, params: Iterable[Any] = ()) -> List[Tuple]:
        cur = self._conn.execute(sql, tuple(params))
        return cur.fetchall()

    def query_one(self, sql: str, params: Iterable[Any] = ()) -> Optional[Tuple]:
        cur = self._conn.execute(sql, tuple(params))
        return cur.fetchone()

    def close(self) -> None:
        self._conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()
```

- [ ] **Step 5.4: 跑測試**

```bash
pytest tests/test_db_libsql.py tests/test_db_client.py -v
```

Expected: 6 + 4 = 10 passed.

確認全測試還是綠:
```bash
pytest tests/ --tb=short -q
```

Expected: ~72-77 passed(前面任務累積)。

- [ ] **Step 5.5: Commit**

```bash
git add db/client.py tests/test_db_libsql.py
git -c user.email=yihuang0903@gmail.com -c user.name=riverkid commit -m "feat(p1): add libsql:// scheme + auth_token to Database

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 6: scripts/migrate_turso.py

**Files:**
- Create: `scripts/__init__.py`(空檔)
- Create: `scripts/migrate_turso.py`

設計:CLI 腳本,讀 `.env` / 環境變數,連 Turso,跑 `migrate(db)`,印結果。**這個腳本只跑一次**(在 user 完成 Task 0 之後)。

無需 unit test — 因為它本身只是 `migrate(Database(libsql_url, token))` 的薄包裝。Smoke test 由 Task 12 涵蓋。

- [ ] **Step 6.1: 建空 scripts/__init__.py**

```bash
touch scripts/__init__.py
```

- [ ] **Step 6.2: 寫 scripts/migrate_turso.py**

```python
"""One-shot migration runner for Turso.

Usage:
    # Set TURSO_DB_URL and TURSO_AUTH_TOKEN in .env or env vars
    python -m scripts.migrate_turso
"""
import os
import sys
from pathlib import Path

# Load .env if present (no python-dotenv dep needed for this trivial case)
_env_path = Path(__file__).resolve().parents[1] / ".env"
if _env_path.exists():
    for line in _env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())

from db.client import Database
from schema.migrate import migrate


def main() -> int:
    url = os.environ.get("TURSO_DB_URL") or os.environ.get("DB_URL", "")
    token = os.environ.get("TURSO_AUTH_TOKEN") or os.environ.get("DB_AUTH_TOKEN", "")
    if not url:
        print("ERROR: TURSO_DB_URL (or DB_URL) not set", file=sys.stderr)
        return 1
    if url.startswith("libsql://") and not token:
        print("ERROR: TURSO_AUTH_TOKEN (or DB_AUTH_TOKEN) not set for libsql", file=sys.stderr)
        return 1

    print(f"Connecting to: {url}")
    with Database(url, auth_token=token if token else None) as db:
        applied = migrate(db)
        print(f"Applied versions: {applied}")
    print("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 6.3: 本機 dry-run(使用 sqlite,不需要 Turso)**

```bash
cd /c/Projects/crypto-ai-agent && source venv/Scripts/activate
# 用本機 sqlite 試一下
DB_URL=sqlite:///state/test_migrate.db python -m scripts.migrate_turso
```

Expected output:
```
Connecting to: sqlite:///state/test_migrate.db
Applied versions: [1, 2]
Done.
```

再跑一次應該:
```
Applied versions: []
Done.
```

清理:
```bash
rm state/test_migrate.db
```

- [ ] **Step 6.4: Commit**

```bash
git add scripts/__init__.py scripts/migrate_turso.py
git -c user.email=yihuang0903@gmail.com -c user.name=riverkid commit -m "feat(p1): add scripts/migrate_turso.py one-shot migration runner

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 7: Binance Adapter

**Files:**
- Create: `adapters/exchanges/binance.py`
- Create: `tests/test_binance.py`

設計:`BinanceExchange(api_key, api_secret, testnet=True)`,實作 Exchange protocol(`get_price`、`place_order`、`cancel`)。內部用 `python-binance` 的 `Client`,testnet 透過 `Client(api_key, api_secret, testnet=True)` 設定。

測試策略:用 `unittest.mock.patch` 把 `binance.client.Client` 全 mock。**絕對不打真 testnet,否則 CI 會卡**。

實作參考:
- `client.get_symbol_ticker(symbol)` → `{"symbol": "BTCUSDT", "price": "60000.0"}`
- `client.create_order(symbol=..., side="BUY", type="MARKET", quantity=...)` → 完整 order dict,包含 `orderId`, `status`, `fills` 等
- `client.cancel_order(symbol=..., orderId=...)` → 同上

- [ ] **Step 7.1: 寫 tests/test_binance.py**

```python
from unittest.mock import MagicMock, patch
import pytest
from adapters.exchanges.binance import BinanceExchange
from adapters.exchanges.base import ExchangeOrder


@patch("adapters.exchanges.binance.Client")
def test_get_price_uses_get_symbol_ticker(MockClient):
    mock_client = MagicMock()
    mock_client.get_symbol_ticker.return_value = {"symbol": "BTCUSDT", "price": "60000.5"}
    MockClient.return_value = mock_client

    ex = BinanceExchange(api_key="k", api_secret="s", testnet=True)
    price = ex.get_price("BTCUSDT")

    MockClient.assert_called_once_with("k", "s", testnet=True)
    mock_client.get_symbol_ticker.assert_called_once_with(symbol="BTCUSDT")
    assert price == 60000.5


@patch("adapters.exchanges.binance.Client")
def test_get_price_propagates_unknown_symbol(MockClient):
    from binance.exceptions import BinanceAPIException
    mock_client = MagicMock()
    mock_client.get_symbol_ticker.side_effect = BinanceAPIException(
        MagicMock(status_code=400), 400, '{"code":-1121,"msg":"Invalid symbol."}'
    )
    MockClient.return_value = mock_client
    ex = BinanceExchange(api_key="k", api_secret="s", testnet=True)
    with pytest.raises(BinanceAPIException):
        ex.get_price("UNKNOWN")


@patch("adapters.exchanges.binance.Client")
def test_place_market_buy_returns_exchange_order(MockClient):
    mock_client = MagicMock()
    mock_client.create_order.return_value = {
        "symbol": "BTCUSDT", "orderId": 12345, "status": "FILLED",
        "executedQty": "0.001", "cummulativeQuoteQty": "60.0",
        "fills": [
            {"price": "60000.0", "qty": "0.001", "commission": "0.06", "commissionAsset": "USDT"},
        ],
    }
    MockClient.return_value = mock_client
    ex = BinanceExchange(api_key="k", api_secret="s", testnet=True)

    order = ex.place_order("BTCUSDT", "buy", qty=0.001, type="market")

    mock_client.create_order.assert_called_once_with(
        symbol="BTCUSDT", side="BUY", type="MARKET", quantity=0.001,
    )
    assert isinstance(order, ExchangeOrder)
    assert order.id == "12345"
    assert order.status == "filled"
    assert order.fill_qty == 0.001
    assert order.fill_price == 60000.0
    assert order.fee_usdt == 0.06


@patch("adapters.exchanges.binance.Client")
def test_place_market_sell(MockClient):
    mock_client = MagicMock()
    mock_client.create_order.return_value = {
        "symbol": "BTCUSDT", "orderId": 99, "status": "FILLED",
        "executedQty": "0.001",
        "fills": [{"price": "60000.0", "qty": "0.001", "commission": "0.06", "commissionAsset": "USDT"}],
    }
    MockClient.return_value = mock_client
    ex = BinanceExchange(api_key="k", api_secret="s", testnet=True)
    order = ex.place_order("BTCUSDT", "sell", qty=0.001, type="market")
    mock_client.create_order.assert_called_once_with(
        symbol="BTCUSDT", side="SELL", type="MARKET", quantity=0.001,
    )
    assert order.status == "filled"


@patch("adapters.exchanges.binance.Client")
def test_place_order_partial_fill(MockClient):
    mock_client = MagicMock()
    mock_client.create_order.return_value = {
        "symbol": "BTCUSDT", "orderId": 5, "status": "PARTIALLY_FILLED",
        "executedQty": "0.0005",
        "fills": [{"price": "60000.0", "qty": "0.0005", "commission": "0.03", "commissionAsset": "USDT"}],
    }
    MockClient.return_value = mock_client
    ex = BinanceExchange(api_key="k", api_secret="s", testnet=True)
    order = ex.place_order("BTCUSDT", "buy", qty=0.001, type="market")
    assert order.status == "partial"
    assert order.fill_qty == 0.0005


@patch("adapters.exchanges.binance.Client")
def test_cancel_returns_true_on_success(MockClient):
    mock_client = MagicMock()
    mock_client.cancel_order.return_value = {"orderId": 12345, "status": "CANCELED"}
    MockClient.return_value = mock_client
    ex = BinanceExchange(api_key="k", api_secret="s", testnet=True)
    # cancel requires symbol — passed via second-positional or kwarg
    ok = ex.cancel("12345", symbol="BTCUSDT")
    assert ok is True


@patch("adapters.exchanges.binance.Client")
def test_cancel_returns_false_on_error(MockClient):
    from binance.exceptions import BinanceAPIException
    mock_client = MagicMock()
    mock_client.cancel_order.side_effect = BinanceAPIException(
        MagicMock(status_code=400), 400, '{"code":-2011,"msg":"Unknown order."}'
    )
    MockClient.return_value = mock_client
    ex = BinanceExchange(api_key="k", api_secret="s", testnet=True)
    ok = ex.cancel("99999", symbol="BTCUSDT")
    assert ok is False


@patch("adapters.exchanges.binance.Client")
def test_fee_extracted_only_when_quote_is_usdt(MockClient):
    """If commission asset isn't USDT (e.g., BNB discount), fee_usdt=0 in P1."""
    mock_client = MagicMock()
    mock_client.create_order.return_value = {
        "symbol": "BTCUSDT", "orderId": 1, "status": "FILLED",
        "executedQty": "0.001",
        "fills": [{"price": "60000.0", "qty": "0.001", "commission": "0.0001", "commissionAsset": "BNB"}],
    }
    MockClient.return_value = mock_client
    ex = BinanceExchange(api_key="k", api_secret="s", testnet=True)
    order = ex.place_order("BTCUSDT", "buy", qty=0.001, type="market")
    assert order.fee_usdt == 0  # BNB fee not converted in P1; P2 can fix
```

- [ ] **Step 7.2: 跑測試確認 fail**

```bash
pytest tests/test_binance.py -v
```

Expected: ImportError for `adapters.exchanges.binance`

- [ ] **Step 7.3: 寫 adapters/exchanges/binance.py**

```python
"""Binance adapter (testnet & live, spot-only for P1)."""
from typing import Optional
from binance.client import Client
from binance.exceptions import BinanceAPIException
from adapters.exchanges.base import ExchangeOrder


# Binance order status -> our normalized status
_STATUS_MAP = {
    "NEW": "new",
    "PARTIALLY_FILLED": "partial",
    "FILLED": "filled",
    "CANCELED": "cancelled",
    "EXPIRED": "cancelled",
    "REJECTED": "failed",
}


class BinanceExchange:
    def __init__(self, api_key: str, api_secret: str, testnet: bool = True):
        self._client = Client(api_key, api_secret, testnet=testnet)

    def get_price(self, symbol: str) -> float:
        ticker = self._client.get_symbol_ticker(symbol=symbol)
        return float(ticker["price"])

    def place_order(self, symbol: str, side: str, qty: float,
                    price: Optional[float] = None, type: str = "market") -> ExchangeOrder:
        if type != "market":
            raise NotImplementedError("P1 only supports market orders")
        order = self._client.create_order(
            symbol=symbol,
            side=side.upper(),
            type="MARKET",
            quantity=qty,
        )
        return _order_dict_to_exchange_order(order)

    def cancel(self, exchange_order_id: str, symbol: Optional[str] = None) -> bool:
        # NOTE: Binance requires symbol AND orderId for cancel.
        # The Exchange Protocol takes only id; P0 fake exchange returns False.
        # Here we accept symbol as a kwarg for callers who have it.
        if symbol is None:
            return False
        try:
            self._client.cancel_order(symbol=symbol, orderId=int(exchange_order_id))
            return True
        except BinanceAPIException:
            return False


def _order_dict_to_exchange_order(order: dict) -> ExchangeOrder:
    """Convert Binance create_order response dict to our ExchangeOrder."""
    status = _STATUS_MAP.get(order.get("status", ""), "failed")
    executed_qty = float(order.get("executedQty", 0) or 0)

    # Weighted-average fill price from `fills` array
    fills = order.get("fills", [])
    if fills and executed_qty > 0:
        total_quote = sum(float(f["price"]) * float(f["qty"]) for f in fills)
        fill_price = total_quote / executed_qty
    else:
        fill_price = None

    # Fee: only count USDT-denominated commissions in P1
    fee_usdt = sum(
        float(f.get("commission", 0))
        for f in fills
        if f.get("commissionAsset") == "USDT"
    )

    return ExchangeOrder(
        id=str(order.get("orderId", "")),
        status=status,
        fill_qty=executed_qty,
        fill_price=fill_price,
        fee_usdt=fee_usdt,
    )
```

- [ ] **Step 7.4: 跑測試**

```bash
pytest tests/test_binance.py -v
```

Expected: 8 passed.

跑全測試:
```bash
pytest tests/ --tb=short -q
```

Expected: 全綠(累積 ~80 passed)。

- [ ] **Step 7.5: Commit**

```bash
git add adapters/exchanges/binance.py tests/test_binance.py
git -c user.email=yihuang0903@gmail.com -c user.name=riverkid commit -m "feat(p1): add BinanceExchange adapter (testnet, market-only, mocked tests)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 8: scripts/seed_signal.py CLI

**Files:**
- Create: `scripts/seed_signal.py`

設計:CLI 工具,使用者本機跑(讀 `.env` 連 Turso),寫一筆 signal 到 Turso。預設參數合理,所以 `python -m scripts.seed_signal` 不帶任何參數就能跑出一筆「BTCUSDT market buy $50」測試 signal。

無需 unit test — 跟 migrate_turso.py 一樣是薄包裝。Smoke test 由 Task 12 涵蓋。

- [ ] **Step 8.1: 寫 scripts/seed_signal.py**

```python
"""Seed a test signal into the cloud DB.

Usage:
    python -m scripts.seed_signal                            # default: BTCUSDT market $50
    python -m scripts.seed_signal --symbol ETHUSDT --size 100
    python -m scripts.seed_signal --symbol BTCUSDT --entry 60000 --stop 58000 --target 65000 --size 50
"""
import argparse
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Load .env
_env_path = Path(__file__).resolve().parents[1] / ".env"
if _env_path.exists():
    for line in _env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())

from db.client import Database
from db.repos.signals import Signals
from db.repos.strategies import Strategies


DEFAULT_UNIVERSE = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", default="BTCUSDT", help="Trading pair (default: BTCUSDT)")
    parser.add_argument("--size", type=float, default=50.0, help="Position size in USDT (default: 50)")
    parser.add_argument("--entry", type=float, default=None,
                        help="Entry price (omit = market entry)")
    parser.add_argument("--stop", type=float, default=None, help="Stop-loss price")
    parser.add_argument("--target", type=float, default=None, help="Take-profit price")
    parser.add_argument("--expires-hours", type=int, default=24,
                        help="Signal expiry in hours (default: 24)")
    parser.add_argument("--strategy", default="trend_majors", help="Strategy name (default: trend_majors)")
    parser.add_argument("--reason", default="manual seed (P1 smoke)", help="Reason text")
    args = parser.parse_args()

    url = os.environ.get("TURSO_DB_URL") or os.environ.get("DB_URL", "")
    token = os.environ.get("TURSO_AUTH_TOKEN") or os.environ.get("DB_AUTH_TOKEN", "")
    if not url:
        print("ERROR: TURSO_DB_URL not set", file=sys.stderr)
        return 1

    expires_at = (datetime.now(timezone.utc) + timedelta(hours=args.expires_hours)).isoformat()

    with Database(url, auth_token=token if token else None) as db:
        # Ensure strategy exists with default universe (idempotent)
        strategies = Strategies(db)
        strategy = strategies.get_by_name(args.strategy)
        if strategy is None:
            sid = strategies.insert(name=args.strategy, params={"universe": DEFAULT_UNIVERSE})
            print(f"Inserted new strategy '{args.strategy}' with universe {DEFAULT_UNIVERSE}, id={sid}")
        else:
            sid = strategy.id
            print(f"Using existing strategy '{args.strategy}' id={sid}, universe={strategy.params.get('universe')}")

        signals = Signals(db)
        signal_id = signals.insert(
            strategy_id=sid, symbol=args.symbol, side="long",
            entry_price=args.entry, stop_price=args.stop, target_price=args.target,
            size_usdt=args.size, expires_at=expires_at, reason=args.reason,
        )
        print(f"Inserted signal: id={signal_id} symbol={args.symbol} size_usdt={args.size} "
              f"entry={args.entry} stop={args.stop} target={args.target}")
        print(f"Expires: {expires_at}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 8.2: 本機 dry-run(對本機 sqlite,然後清理)**

```bash
cd /c/Projects/crypto-ai-agent && source venv/Scripts/activate
DB_URL=sqlite:///state/test_seed.db python -m scripts.migrate_turso
DB_URL=sqlite:///state/test_seed.db python -m scripts.seed_signal --symbol BTCUSDT --size 50

# 驗證有寫進去
python -c "
from db.client import Database
db = Database('sqlite:///state/test_seed.db')
rows = db.query('SELECT id, symbol, size_usdt, status FROM signals')
print('signals:', rows)
db.close()
"

# 清理
rm state/test_seed.db
```

Expected: 看到 `Inserted signal: id=1 symbol=BTCUSDT ...` + `signals: [(1, 'BTCUSDT', 50.0, 'pending')]`

- [ ] **Step 8.3: Commit**

```bash
git add scripts/seed_signal.py
git -c user.email=yihuang0903@gmail.com -c user.name=riverkid commit -m "feat(p1): add scripts/seed_signal.py CLI for manual signal injection

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 9: GitHub Actions exec_tick.yml(cron 每 5 分鐘)

**Files:**
- Create: `.github/workflows/exec_tick.yml`

設計:GHA cron 每 5 分鐘跑一次 `python -m executor.tick`(非 --fake 模式),讀 Turso、打 Binance testnet。失敗時透過 GitHub built-in 機制 + Discord webhook 通知。

注意:GHA cron 最快 5 分鐘,且實際排程有漂移(可能延遲 5-15 分鐘),這是 GHA 的物理限制。

- [ ] **Step 9.1: 寫 .github/workflows/exec_tick.yml**

```yaml
name: exec_tick

on:
  schedule:
    # Every 5 minutes. GHA cron is best-effort and may drift 5-15 min.
    - cron: '*/5 * * * *'
  workflow_dispatch:
    inputs:
      strategy:
        description: 'Strategy name (default: trend_majors)'
        required: false
        default: 'trend_majors'

permissions:
  contents: read

jobs:
  tick:
    runs-on: ubuntu-latest
    timeout-minutes: 5
    concurrency:
      group: exec_tick
      cancel-in-progress: false  # Don't kill an in-flight tick
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: 'pip'

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Run tick
        env:
          DB_URL: ${{ secrets.TURSO_DB_URL }}
          DB_AUTH_TOKEN: ${{ secrets.TURSO_AUTH_TOKEN }}
          BINANCE_API_KEY: ${{ secrets.BINANCE_API_KEY }}
          BINANCE_API_SECRET: ${{ secrets.BINANCE_API_SECRET }}
          BINANCE_TESTNET: 'true'
          CHAT_NOTIFY_HUB_URL: ${{ secrets.CHAT_NOTIFY_HUB_URL }}
        run: |
          python -m executor.tick --strategy "${{ inputs.strategy || 'trend_majors' }}"
```

- [ ] **Step 9.2: 本機 lint(yamllint 不裝也行,直接 cat 看格式)**

```bash
cat .github/workflows/exec_tick.yml | head -30
```

確認:
- `cron: '*/5 * * * *'` 是 every 5 minutes
- 5 個 secrets 都有 ref
- `python-version: '3.11'` 跟你本機一致

- [ ] **Step 9.3: Commit**

```bash
git add .github/workflows/exec_tick.yml
git -c user.email=yihuang0903@gmail.com -c user.name=riverkid commit -m "feat(p1): add GHA exec_tick workflow (cron */5min + workflow_dispatch)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 10: GitHub Actions exec_manual.yml(workflow_dispatch + seed)

**Files:**
- Create: `.github/workflows/exec_manual.yml`

設計:純手動 workflow,可以直接從 GitHub Actions UI 跑。提供兩個動作:`seed`(注入 signal)和 `tick`(立刻跑一次 tick,不等 cron)。

- [ ] **Step 10.1: 寫 .github/workflows/exec_manual.yml**

```yaml
name: exec_manual

on:
  workflow_dispatch:
    inputs:
      action:
        description: 'Action to run'
        required: true
        default: 'tick'
        type: choice
        options:
          - tick
          - seed
          - migrate
      symbol:
        description: 'Symbol for seed (e.g. BTCUSDT)'
        required: false
        default: 'BTCUSDT'
      size_usdt:
        description: 'Size USDT for seed (e.g. 50)'
        required: false
        default: '50'

permissions:
  contents: read

jobs:
  run:
    runs-on: ubuntu-latest
    timeout-minutes: 5
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: 'pip'
      - run: pip install -r requirements.txt

      - name: Run migrate
        if: inputs.action == 'migrate'
        env:
          TURSO_DB_URL: ${{ secrets.TURSO_DB_URL }}
          TURSO_AUTH_TOKEN: ${{ secrets.TURSO_AUTH_TOKEN }}
        run: python -m scripts.migrate_turso

      - name: Run seed
        if: inputs.action == 'seed'
        env:
          TURSO_DB_URL: ${{ secrets.TURSO_DB_URL }}
          TURSO_AUTH_TOKEN: ${{ secrets.TURSO_AUTH_TOKEN }}
        run: |
          python -m scripts.seed_signal \
            --symbol "${{ inputs.symbol }}" \
            --size "${{ inputs.size_usdt }}"

      - name: Run tick
        if: inputs.action == 'tick'
        env:
          DB_URL: ${{ secrets.TURSO_DB_URL }}
          DB_AUTH_TOKEN: ${{ secrets.TURSO_AUTH_TOKEN }}
          BINANCE_API_KEY: ${{ secrets.BINANCE_API_KEY }}
          BINANCE_API_SECRET: ${{ secrets.BINANCE_API_SECRET }}
          BINANCE_TESTNET: 'true'
          CHAT_NOTIFY_HUB_URL: ${{ secrets.CHAT_NOTIFY_HUB_URL }}
        run: python -m executor.tick
```

- [ ] **Step 10.2: 驗證 + Commit**

```bash
cat .github/workflows/exec_manual.yml | grep -E "^name|action|symbol"

git add .github/workflows/exec_manual.yml
git -c user.email=yihuang0903@gmail.com -c user.name=riverkid commit -m "feat(p1): add GHA exec_manual workflow (tick / seed / migrate via UI)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 11: docs/P1_SETUP.md(使用者操作說明)

**Files:**
- Create: `docs/P1_SETUP.md`

- [ ] **Step 11.1: 寫 docs/P1_SETUP.md(完整步驟,Task 0 的擴充版)**

```markdown
# crypto-ai-agent P1 Setup Guide

P1 之後,系統會 24/7 在雲端跑(GitHub Actions cron),你本機不用一直開。
這份文件是「從 0 到第一筆 testnet 成交」的完整步驟。

預計 30–60 分鐘可以做完。

---

## 1. Turso(雲端 SQLite)

1. 註冊:https://turso.tech(用 GitHub 登入最快)
2. 安裝 CLI(可選,Web UI 也能完成全部步驟):
   ```bash
   # Windows (PowerShell)
   irm https://get.tur.so/install.ps1 | iex
   # macOS / Linux
   curl -sSfL https://get.tur.so/install.sh | bash
   ```
3. 登入並建 DB:
   ```bash
   turso auth login
   turso db create crypto-ai-agent --location nrt   # nrt = 東京;最近的 region
   ```
4. 取得 URL 與 token:
   ```bash
   turso db show crypto-ai-agent --url        # libsql://crypto-ai-agent-<you>.turso.io
   turso db tokens create crypto-ai-agent     # eyJ...(很長的 JWT)
   ```
5. 把 URL 和 token 記下來(待會兩個地方都會用到)。

## 2. Binance testnet

1. 開 https://testnet.binance.vision/,用 GitHub 登入
2. 「Generate HMAC_SHA256 Key」→ 取得 API Key 和 Secret
3. 預設你會有一些 testnet USDT / BTC;不夠的話點「Faucet」拿更多

## 3. chat-notify-hub(可選但建議)

你自己有的 `chat-notify-hub` 專案要先跑起來、有一個 HTTP endpoint 接收 POST。
P1 的訊息格式是:
```json
POST /notify
Content-Type: application/json

{"type": "fill", "severity": "info", "payload": {"symbol": "BTCUSDT", ...}}
```
chat-notify-hub 自己解析後丟到 Discord / Telegram。

如果你 chat-notify-hub 還沒準備好,P1 也可以暫時用 Discord webhook 直接接(但 payload 格式 Discord 不認,只能收到 raw JSON;勉強夠用)。

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

## 7. 第一次跑 migrate(把 P0 的 schema 推到 Turso)

從 GitHub Actions UI:
1. Repo → Actions → `exec_manual` → Run workflow
2. Action 選 `migrate`,Run
3. 30 秒後看到 green check;log 裡會印 `Applied versions: [1, 2]`

或本機跑(產出一樣):
```bash
cd C:\Projects\crypto-ai-agent && source venv/Scripts/activate
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

Workflow 跑完後檢查:
1. Binance testnet 帳戶(https://testnet.binance.vision/en/my/dashboard)應該看到一筆 BTC 買單成交
2. chat-notify-hub / Discord 應該收到 `type=fill` 訊息
3. Turso DB:`turso db shell crypto-ai-agent "SELECT * FROM positions;"` 應該看到 BTCUSDT 持倉

## 10. 接下來:讓它跑 3 天

P1 的 exit criteria:**連續 3 天 cron 跑無 critical error**。所以接下來什麼都不用做,讓系統自己跑。

每天早上花 1 分鐘看:
- Actions 頁 cron 都成功(綠 check)
- chat-notify-hub 沒有 `severity=error` 的訊息
- Binance testnet 帳戶餘額沒爆掉

3 天後 → P2 開工(把 Cowork-side 真實策略推理接進來,取代 manual seed)。

## 緊急停止

如果發現有問題要停掉:
1. Repo → Actions → `exec_tick` → 右上 "..." → "Disable workflow"
2. 或:本機跑 `python -m scripts.seed_signal --symbol DUMMY --size 0`(但這沒用 — 真正的 kill switch 要透過 Turso 改 `control` 表)
3. 最簡單的:`turso db shell crypto-ai-agent "UPDATE control SET value='true' WHERE key='kill_switch';"`

## 疑難排解

| 症狀 | 可能原因 | 解法 |
|---|---|---|
| GHA workflow 紅了,log 顯示 `libsql_experimental.OperationalError: SQLITE_AUTH` | TURSO_AUTH_TOKEN 過期 / 錯了 | 重新建 token、更新 secret |
| 紅,`binance.exceptions.BinanceAPIException: Invalid API-key` | API key 沒給 testnet 權限 | 檢查 testnet.binance.vision,重新 generate |
| 跑成功但 testnet 帳戶沒成交 | 你 seed 的 symbol 不在 strategy 的 universe 裡 | seed 時不要改 symbol,用 BTCUSDT/ETHUSDT/SOLUSDT |
| Discord 沒收到通知 | CHAT_NOTIFY_HUB_URL 沒設,或 chat-notify-hub 沒在跑 | 檢查 secret,或先用任意 webhook URL 試 |
```

- [ ] **Step 11.2: Commit**

```bash
git add docs/P1_SETUP.md
git -c user.email=yihuang0903@gmail.com -c user.name=riverkid commit -m "docs(p1): add P1_SETUP.md (Turso/Binance/GitHub/Secrets walkthrough)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 12: End-to-End Testnet Smoke(manual checklist,非 subagent 工作)

**這個 Task 不是 subagent 跑的程式工作,是使用者跟著 `docs/P1_SETUP.md` 第 7–9 節做一次驗證。subagent 不能執行這 Task。**

- [ ] **Step 12.1**:使用者完成 P1_SETUP.md 第 1–6 節(外部準備)
- [ ] **Step 12.2**:Actions → `exec_manual` → `migrate` → 成功
- [ ] **Step 12.3**:Actions → `exec_manual` → `seed`(BTCUSDT, 50)→ 成功
- [ ] **Step 12.4**:Actions → `exec_manual` → `tick` → 成功
- [ ] **Step 12.5**:打開 testnet.binance.vision 看到一筆 BTC 成交
- [ ] **Step 12.6**:chat-notify-hub / Discord 收到 `type=fill` 訊息
- [ ] **Step 12.7**:5 分鐘後 Actions 頁面看到 cron 自動觸發的 `exec_tick`(green check)
- [ ] **Step 12.8**:`turso db shell crypto-ai-agent "SELECT * FROM positions;"` 看到 BTCUSDT 持倉

如果有任何一步紅,查 P1_SETUP.md 第 10 節「疑難排解」。

完成後 **P1 算是 done**。Exit criteria 還需要「連續 3 天 cron 無 critical error」這條觀察期。

---

## P1 Exit Criteria

對應 spec §11 P1:

| 項目 | 怎麼驗 | 通過 |
|---|---|---|
| `adapters/exchanges/binance.py` 實作 | `pytest tests/test_binance.py` 全綠 | — |
| 實連 testnet | Task 12.5 看到成交 | — |
| Cowork 手動寫 1 個假 signal | `scripts/seed_signal.py` 跑得通 | — |
| GHA 觸發 | Task 12.4 / 12.7 兩個 workflow 都跑成功 | — |
| 收到 testnet fill | Task 12.5 testnet 帳戶有交易紀錄 | — |
| 連續 3 天 cron 跑無 critical error | 觀察期,本 plan 不涵蓋 | (P1.5 觀察期)|
| Discord 收得到通知 | Task 12.6 | — |

## 後續(P2 / P3)

P1 跑滿 3 天觀察期 → 開 P2 plan:
- `pipeline/scan.py`:從 yfinance / Binance public API 拉行情
- `pipeline/strategy.py`:trend_majors 策略邏輯(均線突破等)
- `pipeline/claude_reasoning.md`:Claude prompt 模板
- `bridge/sync_signals.py` + `bridge/push_repo.py` + `bridge/notify_decisions.py`
- Cowork schedule 接好

P3 plan:
- `_START_HERE/*.bat`(7 個控制台)
- stop/target 觸發、平倉邏輯
- `reporter.py` + 每日報告
- daily P&L 計算

每個 phase 各自一份 plan、各自走 subagent-driven flow。
