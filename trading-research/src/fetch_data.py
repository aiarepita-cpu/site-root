"""Download adjusted daily bars from Alpaca into data/<SYMBOL>.csv.

    python3 -m src.fetch_data SPY QQQ IWM

Needs ALPACA_API_KEY / ALPACA_SECRET_KEY (environment or config/.env). Keys are never printed.
Alpaca only has history from the start of its data coverage; for older history, drop CSVs with
columns date,open,close,volume (split/dividend adjusted) into data/ instead.
"""
import csv
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.data import DATA_DIR  # noqa: E402


def fetch(client, symbols, out_dir=DATA_DIR, start=datetime(1990, 1, 1, tzinfo=timezone.utc)):
    from alpaca.data.enums import Adjustment
    from alpaca.data.requests import StockBarsRequest
    from alpaca.data.timeframe import TimeFrame

    req = StockBarsRequest(symbol_or_symbols=list(symbols), timeframe=TimeFrame.Day, start=start,
                           end=datetime.now(timezone.utc) - timedelta(days=1), adjustment=Adjustment.ALL)
    written = {}
    for sym, bars in client.get_stock_bars(req).data.items():
        path = Path(out_dir) / f"{sym}.csv"
        with open(path, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["date", "open", "close", "volume"])
            for b in bars:
                w.writerow([b.timestamp.date().isoformat(), b.open, b.close, b.volume])
        written[sym] = (len(bars), bars[0].timestamp.date() if bars else None)
    return written


def main():
    from src.broker import get_data_client

    for sym, (n, first) in fetch(get_data_client(), sys.argv[1:] or ["SPY", "QQQ", "IWM"]).items():
        print(f"{sym}: {n} bars from {first}")


if __name__ == "__main__":
    main()
