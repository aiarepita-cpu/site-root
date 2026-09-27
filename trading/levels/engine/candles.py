import csv
from dataclasses import dataclass
from datetime import datetime

_TS_FORMATS = (
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%Y.%m.%d %H:%M",
    "%Y-%m-%d",
)


@dataclass
class Candle:
    index: int
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float

    @property
    def body_top(self) -> float:
        return max(self.open, self.close)

    @property
    def body_bottom(self) -> float:
        return min(self.open, self.close)


def _parse_ts(raw: str) -> datetime:
    raw = raw.strip()
    for fmt in _TS_FORMATS:
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    raise ValueError(f"timestamp no reconocido: {raw!r}")


def load_csv(path: str) -> list[Candle]:
    """Carga un CSV OHLC con cabecera flexible (timestamp/date, open, high, low, close)."""
    out: list[Candle] = []
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        cols = {c.lower().strip(): c for c in reader.fieldnames}

        def col(*names: str) -> str:
            for n in names:
                if n in cols:
                    return cols[n]
            raise KeyError(f"falta alguna de {names} en {reader.fieldnames}")

        ts_c = col("timestamp", "date", "time", "datetime")
        o_c, h_c, l_c, c_c = col("open"), col("high"), col("low"), col("close")
        for row in reader:
            out.append(Candle(0, _parse_ts(row[ts_c]), float(row[o_c]),
                              float(row[h_c]), float(row[l_c]), float(row[c_c])))
    out.sort(key=lambda c: c.timestamp)
    for i, c in enumerate(out):
        c.index = i
    return out
