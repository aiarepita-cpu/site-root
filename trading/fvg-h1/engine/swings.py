from .models import Candle, Swing


def detect_swings(candles: list[Candle]) -> list[Swing]:
    """3-candle fractal (1 neighbour each side): the minimal, unambiguous
    definition of a 'local peak/valley of the last move' with no extra
    smoothing parameter invented. A swing at index k is confirmed at k+1
    (it only exists once the next candle closes), which is respected by
    the caller: only swings with index < current_index are usable.
    """
    swings: list[Swing] = []
    n = len(candles)
    for k in range(1, n - 1):
        a, b, c = candles[k - 1], candles[k], candles[k + 1]
        if b.high > a.high and b.high > c.high:
            swings.append(Swing(index=k, price=b.high, body_price=b.body_top, direction="high"))
        if b.low < a.low and b.low < c.low:
            swings.append(Swing(index=k, price=b.low, body_price=b.body_bottom, direction="low"))
    swings.sort(key=lambda s: s.index)
    return swings


def nearest_swing(swings: list[Swing], before_index: int, want: str) -> Swing | None:
    """Nearest confirmed swing of type `want` ('high' or 'low') strictly
    before `before_index`. Swings are confirmed one candle after they
    happen, so a swing at index k is usable only once k + 1 < before_index
    has already elapsed, i.e. k <= before_index - 2.
    """
    best = None
    for s in swings:
        if s.direction != want:
            continue
        if s.index > before_index - 2:
            continue
        if best is None or s.index > best.index:
            best = s
    return best
