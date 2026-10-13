"""Historical daily bars: data/<SYMBOL>.csv with columns date,open,close,volume (split/dividend adjusted).

The final `sealed_fraction` of dates is sealed. dev_data() never returns it; sealed_data()
returns it once per ledger hypothesis and records that use.
"""
import csv
import json
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
CONFIG = json.loads((ROOT / "backtests" / "config.json").read_text())


class SealedPeriodError(RuntimeError):
    pass


def load_csv(symbol, data_dir=DATA_DIR):
    rows = list(csv.DictReader(open(Path(data_dir) / f"{symbol}.csv")))
    return {
        "dates": [date.fromisoformat(r["date"][:10]) for r in rows],
        "open": [float(r["open"]) for r in rows],
        "close": [float(r["close"]) for r in rows],
        "volume": [float(r["volume"]) for r in rows],
    }


def align(bars_by_symbol):
    """Keep only dates present for every symbol."""
    common = sorted(set.intersection(*(set(b["dates"]) for b in bars_by_symbol.values())))
    out = {}
    for s, b in bars_by_symbol.items():
        idx = {d: i for i, d in enumerate(b["dates"])}
        out[s] = {k: [b[k][idx[d]] for d in common] for k in ("open", "close", "volume")}
        out[s]["dates"] = common
    return out


def split_index(n_dates, sealed_fraction=None):
    """Index of the first sealed bar."""
    f = CONFIG["sealed_fraction"] if sealed_fraction is None else sealed_fraction
    if not 0 < f < 1:
        raise ValueError("sealed_fraction must be between 0 and 1")
    return int(n_dates * (1 - f))


def _slice(bars, start, end):
    return {s: {k: v[start:end] for k, v in b.items()} for s, b in bars.items()}


def dev_data(bars, sealed_fraction=None):
    n = len(next(iter(bars.values()))["dates"])
    return _slice(bars, 0, split_index(n, sealed_fraction))


def sealed_data(bars, conn, hypothesis_id, sealed_fraction=None):
    """One use per idea. Returns full history (sealed part needs the earlier bars for indicators)
    plus the index where the sealed period starts. Refuses if already used."""
    row = conn.execute("SELECT sealed_test_result FROM hypotheses WHERE id = ?", (hypothesis_id,)).fetchone()
    if row is None:
        raise SealedPeriodError(f"No hypothesis #{hypothesis_id}")
    if row[0]:
        raise SealedPeriodError(f"Sealed period already used for hypothesis #{hypothesis_id}.")
    conn.execute("UPDATE hypotheses SET sealed_test_result = 'IN USE' WHERE id = ?", (hypothesis_id,))
    conn.commit()
    n = len(next(iter(bars.values()))["dates"])
    return bars, split_index(n, sealed_fraction)
