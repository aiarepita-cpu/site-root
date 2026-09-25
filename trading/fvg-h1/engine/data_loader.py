import csv
from datetime import datetime
from .models import Candle

_TS_FORMATS = (
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%Y.%m.%d %H:%M",
    "%Y-%m-%d",
)


def _parse_ts(raw: str):
    raw = raw.strip()
    for fmt in _TS_FORMATS:
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    try:
        return datetime.fromtimestamp(float(raw))
    except ValueError:
        return raw


def load_ohlc_csv(path: str) -> list[Candle]:
    """Generic H1 OHLC loader. Expects a header with at least:
    timestamp/date/time, open, high, low, close (case-insensitive, any order).
    Extra columns (volume, spread, ...) are ignored.
    """
    candles: list[Candle] = []
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        cols = {c.lower().strip(): c for c in reader.fieldnames}

        def col(*names):
            for n in names:
                if n in cols:
                    return cols[n]
            raise KeyError(f"Missing column among {names} in {reader.fieldnames}")

        ts_col = col("timestamp", "date", "time", "datetime")
        o_col = col("open")
        h_col = col("high")
        l_col = col("low")
        c_col = col("close")

        for i, row in enumerate(reader):
            candles.append(
                Candle(
                    index=i,
                    timestamp=_parse_ts(row[ts_col]),
                    open=float(row[o_col]),
                    high=float(row[h_col]),
                    low=float(row[l_col]),
                    close=float(row[c_col]),
                )
            )
    candles.sort(key=lambda c: c.timestamp if isinstance(c.timestamp, datetime) else c.index)
    for i, c in enumerate(candles):
        c.index = i
    return candles
