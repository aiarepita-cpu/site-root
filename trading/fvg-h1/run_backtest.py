#!/usr/bin/env python3
import argparse
import csv
import sys

from engine.data_loader import load_ohlc_csv
from engine.backtest import run
from engine.metrics import summarize
from engine.models import Direction


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv_path", help="H1 OHLC CSV: timestamp,open,high,low,close")
    ap.add_argument("--trades-out", default="results/trades.csv")
    args = ap.parse_args()

    candles = load_ohlc_csv(args.csv_path)
    if len(candles) < 10:
        print(f"Not enough candles ({len(candles)}) in {args.csv_path}", file=sys.stderr)
        sys.exit(1)

    trades, fvgs = run(candles)

    with open(args.trades_out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow([
            "id", "direction", "entry_ts", "entry_price", "sl_price", "tp_price",
            "rr_planned", "exit_ts", "exit_price", "outcome",
        ])
        for t in trades:
            entry_ts = candles[t.entry_index].timestamp
            exit_ts = candles[t.exit_index].timestamp if t.exit_index is not None else ""
            w.writerow([
                t.id, t.direction.name, entry_ts, t.entry_price, t.sl_price, t.tp_price,
                round(t.rr, 3), exit_ts, t.exit_price, t.outcome or "OPEN",
            ])

    metrics = summarize(trades)
    print(f"Candles loaded : {len(candles)}")
    print(f"FVGs formed    : {len(fvgs)}")
    for k, v in metrics.items():
        print(f"{k:18s}: {v}")


if __name__ == "__main__":
    main()
