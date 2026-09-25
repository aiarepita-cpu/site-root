from .models import Candle, Direction, FVG, FVGState, Trade
from .swings import detect_swings
from .trend import TrendTracker
from .fvg_detector import detect_new_fvg, step_fvg


def run(candles: list[Candle]) -> tuple[list[Trade], list[FVG]]:
    swings = detect_swings(candles)
    tracker = TrendTracker(swings)

    fvgs: list[FVG] = []
    active: list[FVG] = []
    trades: list[Trade] = []
    open_trade: Trade | None = None
    next_fvg_id = 0
    next_trade_id = 0

    for i, candle in enumerate(candles):
        trend = tracker.update(candle)

        # 1) manage an already-open trade (only one at a time: while a
        #    trade is open we do not evaluate new entries, but FVG
        #    detection/tracking keeps running so nothing is missed).
        if open_trade is not None and candle.index > open_trade.entry_index:
            outcome = _resolve_bar(open_trade, candle)
            if outcome:
                open_trade.exit_index = candle.index
                open_trade.exit_price = outcome[1]
                open_trade.outcome = outcome[0]
                open_trade = None

        # 2) advance every still-active FVG
        still_active = []
        for fvg in active:
            trade = step_fvg(fvg, candle, swings)
            if trade is not None and open_trade is None:
                trade.id = next_trade_id
                next_trade_id += 1
                trades.append(trade)
                open_trade = trade
            if fvg.state in (FVGState.WATCHING, FVGState.TOUCHED):
                still_active.append(fvg)
        active = still_active

        # 3) look for a brand-new FVG on this candle
        new_fvg = detect_new_fvg(candles, i, trend, swings)
        if new_fvg is not None:
            new_fvg.id = next_fvg_id
            next_fvg_id += 1
            fvgs.append(new_fvg)
            active.append(new_fvg)

    return trades, fvgs


def _resolve_bar(trade: Trade, candle: Candle):
    """Decides whether SL or TP was hit on this candle. When both levels
    fall inside the same candle's range we cannot know the true intrabar
    order from OHLC alone, so we conservatively assume SL first (the
    worst case for the trade). This is a modeling assumption, not part
    of the strategy rules, and it only matters for candles where both
    SL and TP sit within [low, high].
    """
    if trade.direction is Direction.BUY:
        hit_sl = candle.low <= trade.sl_price
        hit_tp = candle.high >= trade.tp_price
    else:
        hit_sl = candle.high >= trade.sl_price
        hit_tp = candle.low <= trade.tp_price

    if hit_sl and hit_tp:
        return ("SL", trade.sl_price)
    if hit_sl:
        return ("SL", trade.sl_price)
    if hit_tp:
        return ("TP", trade.tp_price)
    return None
