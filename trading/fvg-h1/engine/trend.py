from .models import Candle, Swing


class TrendTracker:
    """Causal BOS/CHoCH trend tracker.

    - Keeps the most recently CONFIRMED swing high and swing low.
    - A candle's CLOSE breaking above the last swing high => uptrend
      (BOS if already up, CHoCH if it was down/undefined).
    - A candle's CLOSE breaking below the last swing low => downtrend.
    - No lookahead: a swing formed at index k is only usable once
      candle k+1 has closed (see swings.detect_swings).
    """

    def __init__(self, swings: list[Swing]):
        self._swings_by_confirm_index: dict[int, list[Swing]] = {}
        for s in swings:
            self._swings_by_confirm_index.setdefault(s.index + 1, []).append(s)
        self.last_high: Swing | None = None
        self.last_low: Swing | None = None
        self.trend: str | None = None  # "up" / "down" / None

    def update(self, candle: Candle) -> str | None:
        for s in self._swings_by_confirm_index.get(candle.index, []):
            if s.direction == "high":
                self.last_high = s
            else:
                self.last_low = s

        if self.last_high is not None and candle.close > self.last_high.price:
            self.trend = "up"
        elif self.last_low is not None and candle.close < self.last_low.price:
            self.trend = "down"

        return self.trend
