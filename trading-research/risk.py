"""Kill switch (Step 5). Every order goes through check_order before it can reach the broker.

Fails closed: missing or malformed limits or account data block the order.
All *_pct values are percentages (2.0 means 2%).
"""
import json
import math
from pathlib import Path

LIMITS_PATH = Path(__file__).resolve().parent / "config" / "risk.json"
REQUIRED = ("max_daily_loss_pct", "max_drawdown_pct", "max_position_pct", "max_open_positions")


def load_limits(path=None) -> dict:
    limits = json.loads(Path(path or LIMITS_PATH).read_text())
    for k in REQUIRED:
        v = limits.get(k)
        if not isinstance(v, (int, float)) or isinstance(v, bool) or not math.isfinite(v) or v <= 0:
            raise ValueError(f"risk.json: '{k}' missing or not a positive number")
    return limits


def check_order(order: dict, account: dict, limits: dict = None) -> tuple[bool, str]:
    """order: symbol, side ('buy'|'sell'), qty, price.
    account: equity, daily_loss_pct, drawdown_pct, positions {symbol: {'qty', 'market_value'}}.
    Sells that only reduce an existing long are always allowed, so the system can get out
    after a limit is hit. Everything else must pass every limit."""
    try:
        limits = limits if limits is not None else load_limits()
        for k in REQUIRED:
            if k not in limits:
                return False, f"Risk limit '{k}' missing. Order blocked."
        symbol, side = order["symbol"], order["side"]
        qty, price = float(order["qty"]), float(order["price"])
        equity = float(account["equity"])
        positions = account["positions"]
        daily_loss = float(account["daily_loss_pct"])
        drawdown = float(account["drawdown_pct"])
    except (KeyError, TypeError, ValueError, OSError) as e:
        return False, f"Bad order/account/limits data ({e!r}). Order blocked."

    if not (qty > 0 and qty == int(qty)) or price <= 0 or equity <= 0:
        return False, "Quantity, price and equity must be positive (whole shares). Order blocked."

    held_qty = float(positions.get(symbol, {}).get("qty", 0))

    if side == "sell":
        if qty > held_qty:
            return False, f"Sell of {qty:g} exceeds held {held_qty:g} (no shorting). Order blocked."
        return True, "OK (reduces an existing position)"
    if side != "buy":
        return False, f"Unknown side '{side}'. Order blocked."

    if daily_loss >= limits["max_daily_loss_pct"]:
        return False, "Daily loss limit hit. Trading stopped."
    if drawdown >= limits["max_drawdown_pct"]:
        return False, "Max drawdown hit. Trading stopped."

    held_value = float(positions.get(symbol, {}).get("market_value", 0))
    new_value = held_value + qty * price
    if new_value > equity * limits["max_position_pct"] / 100:
        return False, (f"Position would be {new_value / equity:.2%} of equity, above the "
                       f"{limits['max_position_pct']}% limit.")
    if symbol not in positions and len(positions) >= limits["max_open_positions"]:
        return False, "Too many open positions."
    return True, "OK"
