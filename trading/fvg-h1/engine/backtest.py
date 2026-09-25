from .models import Candle, Direction, FVG, FVGState, Trade
from .swings import detect_swings
from .trend import TrendTracker
from .fvg_detector import detect_new_fvg, detect_raw_fvg, step_fvg


def run(
    candles: list[Candle],
    structure_n: int = 1,
    target_n: int = 1,
    require_fvg_break: bool = False,
    fvg_window: int = 2,
    break_fvg_only: bool = False,
) -> tuple[list[Trade], list[FVG]]:
    """`structure_n` sizes the fractal used for trend BOS/CHoCH and for
    the leg-origin SL; `target_n` sizes the (smaller) fractal used to
    pick the nearest opposite swing as TP.

    `require_fvg_break`: a swing is only "broken" if the breaking move
    displaced, leaving an FVG in the same direction (see TrendTracker).
    `break_fvg_only`: trade only the FVG that validated the break that
    started the current leg, instead of every trend-aligned FVG.
    """
    structure_swings = detect_swings(candles, structure_n)
    target_swings = structure_swings if target_n == structure_n else detect_swings(candles, target_n)
    tracker = TrendTracker(structure_swings, structure_n, require_fvg_break, fvg_window)

    fvgs: list[FVG] = []
    active: list[FVG] = []
    trades: list[Trade] = []
    open_trade: Trade | None = None
    next_fvg_id = 0
    next_trade_id = 0
    seen_break_fvgs: set[int] = set()

    for i, candle in enumerate(candles):
        # 0) raw FVG geometry for this candle, so the tracker can decide
        #    whether a break displaced. No trend input here on purpose.
        raw = detect_raw_fvg(candles, i)
        if raw is not None:
            tracker.note_fvg(raw, i)

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
            trade = step_fvg(fvg, candle, target_swings, target_n)
            if trade is not None and open_trade is None:
                trade.id = next_trade_id
                next_trade_id += 1
                trades.append(trade)
                open_trade = trade
            if fvg.state in (FVGState.WATCHING, FVGState.TOUCHED):
                still_active.append(fvg)
        active = still_active

        # 3) look for a brand-new tradeable FVG
        if break_fvg_only:
            # only the FVG that validated this leg's break is tradeable.
            # It may sit a couple of candles BEHIND this one (the break
            # displaced before the close that confirmed it), in which
            # case we activate it now and replay the candles in between
            # so its state is honest -- we could not have watched it
            # before knowing the leg had started.
            bidx = tracker.break_fvg_index
            if bidx is not None and bidx not in seen_break_fvgs:
                seen_break_fvgs.add(bidx)
                new_fvg = detect_new_fvg(
                    candles, bidx, trend, tracker.leg_origin_low, tracker.leg_origin_high
                )
                if new_fvg is not None:
                    for j in range(bidx + 1, i + 1):
                        step_fvg(new_fvg, candles[j], target_swings, target_n)
                    if new_fvg.state in (FVGState.WATCHING, FVGState.TOUCHED):
                        new_fvg.id = next_fvg_id
                        next_fvg_id += 1
                        fvgs.append(new_fvg)
                        active.append(new_fvg)
        else:
            new_fvg = detect_new_fvg(
                candles, i, trend, tracker.leg_origin_low, tracker.leg_origin_high
            )
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
