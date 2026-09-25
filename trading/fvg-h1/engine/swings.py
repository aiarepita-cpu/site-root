from .models import Candle, Swing


def detect_swings(candles: list[Candle], n: int = 1) -> list[Swing]:
    """Fractal swing detection with `n` neighbours on each side (n=1 is
    the classic 3-candle fractal). A swing at index k is confirmed at
    k+n: it only exists once n further candles have closed. Callers must
    respect that lag (see `nearest_swing` and TrendTracker).

    `n` controls how structural the swings are: n=1 marks ~46% of H1
    candles as swings, which is noise, not structure. Use a small n for
    "the nearest local peak" (TP targets) and a larger n for trend
    structure.
    """
    swings: list[Swing] = []
    total = len(candles)
    for k in range(n, total - n):
        b = candles[k]
        is_high = all(
            b.high > candles[k - j].high and b.high > candles[k + j].high
            for j in range(1, n + 1)
        )
        is_low = all(
            b.low < candles[k - j].low and b.low < candles[k + j].low
            for j in range(1, n + 1)
        )
        if is_high:
            swings.append(Swing(index=k, price=b.high, body_price=b.body_top, direction="high"))
        if is_low:
            swings.append(Swing(index=k, price=b.low, body_price=b.body_bottom, direction="low"))
    swings.sort(key=lambda s: s.index)
    return swings


def nearest_swing(swings: list[Swing], before_index: int, want: str, n: int = 1) -> Swing | None:
    """Nearest confirmed swing of type `want` ('high' or 'low') strictly
    before `before_index`. A swing at index k is confirmed at k+n, and
    one extra candle of margin is kept, so it is usable only once
    k + n <= before_index - 1, i.e. k <= before_index - n - 1.
    """
    cutoff = before_index - n - 1
    best = None
    for s in swings:
        if s.direction != want:
            continue
        if s.index > cutoff:
            continue
        if best is None or s.index > best.index:
            best = s
    return best
