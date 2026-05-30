from typing import List, Optional
from db.repos.control import Control
from db.repos.positions import Positions
from db.repos.events import Events


class CircuitBreaker:
    def __init__(self, control: Control, positions: Positions, events: Events):
        self._c = control
        self._p = positions
        self._e = events
        self._api_failures: dict = {}

    def evaluate_new_entry(self, *, symbol: str, size_usdt: float,
                           universe: List[str], daily_realized_pnl: float) -> Optional[str]:
        # 1. universe whitelist (cannot bypass)
        if symbol not in universe:
            return f"universe: {symbol} not in whitelist"

        # 2. kill switch
        if self._c.get_bool("kill_switch", default=False):
            return "kill_switch: enabled"

        # 3. daily loss cap -> auto-trigger kill switch
        max_daily_loss = self._c.get_float("max_daily_loss_usdt", default=300.0)
        if daily_realized_pnl <= -max_daily_loss:
            self._c.set("kill_switch", "true")
            self._e.log("circuit_open", {
                "reason": "daily_loss",
                "daily_realized_pnl": daily_realized_pnl,
                "cap": max_daily_loss,
            })
            return f"daily_loss: realized {daily_realized_pnl:.2f} <= -{max_daily_loss:.2f}"

        # 4. per-trade size cap
        max_per_trade = self._c.get_float("max_per_trade_usdt", default=500.0)
        if size_usdt > max_per_trade:
            return f"max_per_trade: {size_usdt:.2f} > {max_per_trade:.2f}"

        # 5. max concurrent open positions
        max_open = self._c.get_int("max_open_positions", default=3)
        existing_count = self._p.count_open()
        already_have_this = self._p.get_qty(symbol) > 0
        if not already_have_this and existing_count >= max_open:
            return f"max_open_positions: already {existing_count} >= {max_open}"

        # 6. per-symbol position cap
        max_per_symbol = self._c.get_int("max_position_per_symbol", default=1)
        if already_have_this and max_per_symbol <= 1:
            return f"max_position_per_symbol: {symbol} already held"

        return None

    def check_slippage(self, estimated_pct: float) -> Optional[str]:
        cap = self._c.get_float("slippage_max_pct", default=0.01)
        if estimated_pct > cap:
            return f"slippage: {estimated_pct:.4f} > {cap:.4f}"
        return None

    def evaluate_risk_reduction(self) -> Optional[str]:
        return None  # risk reduction always allowed (spec section 8, core principle #2)

    def note_api_failure(self, symbol: str) -> None:
        self._api_failures[symbol] = self._api_failures.get(symbol, 0) + 1

    def note_api_success(self, symbol: str) -> None:
        self._api_failures.pop(symbol, None)

    def should_circuit_open(self, symbol: str) -> bool:
        threshold = self._c.get_int("api_fail_threshold", default=3)
        return self._api_failures.get(symbol, 0) >= threshold
