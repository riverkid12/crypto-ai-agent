from db.repos.signals import Signal


def should_trigger(signal: Signal, current_price: float, holding_qty: float = 0.0) -> bool:
    if signal.side == "long":
        if signal.entry_price is None:
            return True
        return current_price >= signal.entry_price
    if signal.side == "flat":
        return holding_qty > 0
    return False
