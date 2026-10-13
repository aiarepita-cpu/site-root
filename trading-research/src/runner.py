"""Paper-trading runner (Step 5). Run once per trading day before the open:

    python3 -m src.runner

Signals use the latest completed daily bar; market orders fill at the next open.
Only ledger ideas that passed the backtest (including the sealed run) are traded.
Every order goes through risk.check_order first; every decision is journaled.
"""
import importlib.util
import json
import math
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "memory")]

import ledger  # noqa: E402
import risk  # noqa: E402
from src import journal  # noqa: E402
from src.broker import assert_paper  # noqa: E402

STATE_PATH = ROOT / "memory" / "equity_peak.json"


# --- helpers -----------------------------------------------------------------
def load_strategy(path: str):
    spec = importlib.util.spec_from_file_location(Path(path).stem, ROOT / path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def market_conditions(closes, volumes) -> dict:
    c = {"last_close": round(closes[-1], 2)}
    if len(closes) >= 2:
        c["day_return_pct"] = round((closes[-1] / closes[-2] - 1) * 100, 2)
    if len(closes) >= 200:
        sma = sum(closes[-200:]) / 200
        c["vs_sma200_pct"] = round((closes[-1] / sma - 1) * 100, 2)
    if len(closes) >= 21:
        rets = [math.log(closes[i] / closes[i - 1]) for i in range(-20, 0)]
        mean = sum(rets) / 20
        c["vol20_annual_pct"] = round(math.sqrt(sum((r - mean) ** 2 for r in rets) / 19 * 252) * 100, 1)
    if len(volumes) >= 21:
        c["volume_vs_20d"] = round(volumes[-1] / (sum(volumes[-21:-1]) / 20), 2)
    return c


def update_peak(equity: float, state_path=STATE_PATH) -> float:
    peak = equity
    try:
        peak = max(peak, float(json.loads(Path(state_path).read_text())["peak_equity"]))
    except (OSError, ValueError, KeyError):
        pass
    Path(state_path).write_text(json.dumps({"peak_equity": peak}))
    return peak


def history_peak(trading) -> float:
    """Highest daily equity in the account's own history (survives fresh containers)."""
    from alpaca.trading.requests import GetPortfolioHistoryRequest

    try:
        hist = trading.get_portfolio_history(GetPortfolioHistoryRequest(period="all", timeframe="1D"))
        return max((float(e) for e in (hist.equity or []) if e is not None), default=0.0)
    except Exception:  # noqa: BLE001 - fall back to the local high-water mark
        return 0.0


def account_snapshot(trading, state_path=STATE_PATH) -> dict:
    acct = trading.get_account()
    equity, last_equity = float(acct.equity), float(acct.last_equity)
    peak = update_peak(max(equity, history_peak(trading)), state_path)
    positions = {p.symbol: {"qty": float(p.qty), "market_value": float(p.market_value)}
                 for p in trading.get_all_positions()}
    return {
        "equity": equity,
        "daily_loss_pct": max(0.0, (last_equity - equity) / last_equity * 100) if last_equity > 0 else 0.0,
        "drawdown_pct": max(0.0, (peak - equity) / peak * 100),
        "positions": positions,
        "blocked": bool(acct.trading_blocked or acct.account_blocked),
    }


def fetch_bars(data, symbols, now, exclude_date=None):
    """Completed daily bars only: pass exclude_date=today while the session is open
    (today's bar is still forming). Same feed and adjustment as the backtest data."""
    from alpaca.data.enums import Adjustment
    from alpaca.data.requests import StockBarsRequest
    from alpaca.data.timeframe import TimeFrame

    req = StockBarsRequest(symbol_or_symbols=list(symbols), timeframe=TimeFrame.Day,
                           start=now - timedelta(days=420), end=now - timedelta(minutes=20),
                           adjustment=Adjustment.ALL)
    out = {}
    for sym, bars in data.get_stock_bars(req).data.items():
        bars = [b for b in bars if b.timestamp.date() != exclude_date]
        out[sym] = {"dates": [b.timestamp.date() for b in bars],
                    "closes": [float(b.close) for b in bars],
                    "volumes": [float(b.volume) for b in bars]}
    return out


def next_trading_day(trading, after):
    from alpaca.trading.requests import GetCalendarRequest

    days = trading.get_calendar(GetCalendarRequest(start=after + timedelta(days=1),
                                                   end=after + timedelta(days=14)))
    return min(d.date for d in days)


def open_order_symbols(trading) -> set:
    from alpaca.trading.enums import QueryOrderStatus
    from alpaca.trading.requests import GetOrdersRequest

    return {o.symbol for o in trading.get_orders(GetOrdersRequest(status=QueryOrderStatus.OPEN))}


def submit(trading, symbol, side, qty):
    from alpaca.trading.enums import OrderSide, TimeInForce
    from alpaca.trading.requests import MarketOrderRequest

    req = MarketOrderRequest(symbol=symbol, qty=qty, time_in_force=TimeInForce.DAY,
                             side=OrderSide.BUY if side == "buy" else OrderSide.SELL)
    return str(trading.submit_order(order_data=req).id)


# --- strategy adapters: return [(symbol, side or None, qty, reasoning)] ----------
def decide_per_symbol(strat, bars, acct, max_pos_frac, with_volume):
    out = []
    for sym in strat.UNIVERSE:
        b = bars[sym]
        held = acct["positions"].get(sym, {}).get("qty", 0) > 0
        entry = (strat.entry_signal(b["closes"], b["volumes"], held) if with_volume
                 else strat.entry_signal(b["closes"], held))
        if entry:
            qty = strat.position_size(acct["equity"], b["closes"][-1], max_pos_frac)
            out.append((sym, "buy", qty, "Entry rule triggered."))
        elif strat.exit_signal(b["closes"], held):
            out.append((sym, "sell", int(acct["positions"][sym]["qty"]), "Exit rule triggered."))
        else:
            out.append((sym, None, 0, "No entry/exit rule triggered." + (" Holding." if held else " Flat.")))
    return out


def decide_rotation(strat, bars, acct, max_pos_frac, next_day_fn):
    held = [s for s in strat.UNIVERSE if acct["positions"].get(s, {}).get("qty", 0) > 0]
    if len(held) > 1:
        raise RuntimeError(f"Rotation should hold at most one ETF, holds {held}")
    current = held[0] if held else None
    last = bars[strat.UNIVERSE[0]]["dates"][-1]
    rebalance = strat.is_rebalance_day(last, next_day_fn(last))
    closes = {s: bars[s]["closes"] for s in strat.UNIVERSE}
    out = []
    if strat.exit_signal(closes, current, rebalance):
        out.append((current, "sell", int(acct["positions"][current]["qty"]),
                    f"Month-end re-rank: target is now {strat.select_target(closes)}."))
    target = strat.entry_signal(closes, current, rebalance)
    if target:
        qty = strat.position_size(acct["equity"], closes[target][-1], max_pos_frac)
        out.append((target, "buy", qty, "Month-end re-rank: highest positive 6-month return."))
    if not out:
        why = "Not a month-end rebalance day." if not rebalance else "Target unchanged."
        out.append((current or strat.UNIVERSE[0], None, 0, why))
    return out


def decide(strat, bars, acct, max_pos_frac, next_day_fn):
    """Same decision logic for the live runner and the backtester."""
    if strat.STRATEGY_NAME == "relative_strength_rotation":
        return decide_rotation(strat, bars, acct, max_pos_frac, next_day_fn)
    return decide_per_symbol(strat, bars, acct, max_pos_frac,
                             with_volume=strat.STRATEGY_NAME == "volume_breakout")


# --- main loop -------------------------------------------------------------------
def run_once(trading, data, conn, now=None, limits=None, journal_dir=None, state_path=STATE_PATH):
    now = now or datetime.now(timezone.utc)
    log = lambda **kw: journal.log_decision(now=now, journal_dir=journal_dir, **kw)  # noqa: E731

    eligible = ledger.eligible_for_paper(conn)
    for h in ledger.search(conn):
        if h not in eligible:
            log(strategy=Path(h["strategy_file"] or "?").stem, version=h["strategy_version"],
                decision="SKIPPED", market_conditions={},
                reasoning=f"Ledger status '{h['status']}': not cleared for paper trading "
                          "(needs a passed backtest including the sealed run).")
    if not eligible:
        return
    if len(eligible) > 1:
        log(strategy="runner", version="-", decision="ERROR", market_conditions={},
            reasoning="More than one strategy cleared; they would share one paper account and "
                      "positions could not be attributed. Nothing traded.")
        return

    h = eligible[0]
    strat = load_strategy(h["strategy_file"])
    name, version = strat.STRATEGY_NAME, strat.VERSION
    if version != h["strategy_version"]:
        log(strategy=name, version=version, decision="ERROR", market_conditions={},
            reasoning=f"File version {version} != ledger version {h['strategy_version']}. Nothing traded.")
        return

    limits = limits if limits is not None else risk.load_limits()
    assert_paper(trading)
    acct = account_snapshot(trading, state_path)
    if acct["blocked"]:
        log(strategy=name, version=version, decision="ERROR", market_conditions={},
            reasoning="Alpaca reports the paper account as blocked. Nothing traded.")
        return

    clock = trading.get_clock()
    bars = fetch_bars(data, strat.UNIVERSE, now,
                      exclude_date=clock.timestamp.date() if clock.is_open else None)
    max_pos_frac = limits["max_position_pct"] / 100
    intents = decide(strat, bars, acct, max_pos_frac, lambda d: next_trading_day(trading, d))

    pending = open_order_symbols(trading)
    for sym, side, qty, why in intents:
        conds = {"symbol": sym, **market_conditions(bars[sym]["closes"], bars[sym]["volumes"])}
        if side is None:
            log(strategy=name, version=version, decision="HOLD", reasoning=why, market_conditions=conds)
            continue
        order = {"symbol": sym, "side": side, "qty": qty, "price": bars[sym]["closes"][-1]}
        if sym in pending:
            log(strategy=name, version=version, decision="SKIPPED", market_conditions=conds, order=order,
                reasoning=why + " An order for this symbol is already open; not sending another.")
            continue
        ok, reason = risk.check_order(order, acct, limits)
        if not ok:
            log(strategy=name, version=version, decision="BLOCKED", market_conditions=conds,
                order=order, risk_check=reason, reasoning=why)
            continue
        order_id = submit(trading, sym, side, qty)
        log(strategy=name, version=version, decision=side.upper(), market_conditions=conds,
            order=order, risk_check=reason, reasoning=why, order_id=order_id)


def main():
    from src.broker import get_data_client, get_trading_client

    with ledger.connect() as conn:
        run_once(get_trading_client(), get_data_client(), conn)


if __name__ == "__main__":
    main()
