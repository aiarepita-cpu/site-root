"""Backtester (Step 4). Uses the development period only; the sealed final 30% is never read here.

    python3 -m src.backtest --strategy trend_filter_200_v1 --hypothesis 1

Refuses to run without backtests/<strategy>-prediction.md, and refuses if that file changed
after its first run. Every run counts as one variation in the ledger (feeds the Deflated Sharpe).
Signals use the close of day t; orders fill at the open of day t+1 (+delay), with costs.
"""
import argparse
import hashlib
import json
import math
import sys
from datetime import date
from pathlib import Path
from statistics import NormalDist

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "memory")]

import ledger  # noqa: E402
from src import data as data_mod  # noqa: E402
from src.runner import decide, load_strategy  # noqa: E402

BT_DIR = ROOT / "backtests"
CONFIG = data_mod.CONFIG
WARMUP = 252  # bars of history before any window starts trading (covers the 200-day SMA)
EULER_GAMMA = 0.5772156649015329
N01 = NormalDist()


# --- simulation --------------------------------------------------------------------
def _view(bars, t):
    """Bars up to and including t, in the shape the runner's decide() expects."""
    return {s: {"dates": b["dates"][:t + 1], "closes": b["close"][:t + 1], "volumes": b["volume"][:t + 1]}
            for s, b in bars.items()}


def simulate(strat, bars, start, end, cost_mult=1.0, delay=0, max_pos_frac=1.0, capital=100_000.0):
    """Trade from bar `start` to bar `end` (exclusive), flat at start. Returns equity curve and trades."""
    cost = (CONFIG["cost_bps_per_side"] + CONFIG["slippage_bps_per_side"]) * cost_mult / 1e4
    dates = next(iter(bars.values()))["dates"]
    cash, pos, open_trades, trades, equity = capital, {}, {}, [], []
    pending = []  # (fill_index, symbol, side, qty)

    def mark(t):
        return cash + sum(q * bars[s]["close"][t] for s, q in pos.items())

    for t in range(start, end):
        # 1) fills scheduled for today's open
        for fill_t, sym, side, qty in [p for p in pending if p[0] == t]:
            px = bars[sym]["open"][t]
            if side == "sell":
                qty = pos.get(sym, 0)
                if qty <= 0:
                    continue
                cash += qty * px * (1 - cost)
                pos.pop(sym)
                e = open_trades.pop(sym)
                trades.append({"symbol": sym, "entry": e["date"], "exit": dates[t].isoformat(),
                               "pnl": qty * px * (1 - cost) - e["cost"]})
            else:
                fill_px = px * (1 + cost)
                qty = min(qty, math.floor(cash / fill_px))
                if qty <= 0:
                    continue
                cash -= qty * fill_px
                pos[sym] = pos.get(sym, 0) + qty
                e = open_trades.setdefault(sym, {"date": dates[t].isoformat(), "cost": 0.0})
                e["cost"] += qty * fill_px
        pending = [p for p in pending if p[0] > t]

        eq = mark(t)
        equity.append(eq)
        if t + 1 + delay >= end:
            continue  # no fill possible inside the window
        # 2) decide on today's close (positions include orders already pending as "held" only once filled)
        acct = {"equity": eq, "positions": {s: {"qty": q, "market_value": q * bars[s]["close"][t]}
                                            for s, q in pos.items()}}
        pending_syms = {p[1] for p in pending}
        for sym, side, qty, _why in decide(strat, _view(bars, t), acct, max_pos_frac,
                                           lambda d, t=t: dates[t + 1]):
            if side and sym not in pending_syms:
                pending.append((t + 1 + delay, sym, side, qty))

    open_pnl = sum(pos[s] * bars[s]["close"][end - 1] - open_trades[s]["cost"] for s in pos)
    return {"equity": equity, "trades": trades, "open_trades": len(pos), "open_pnl": open_pnl,
            "start": dates[start].isoformat(), "end": dates[end - 1].isoformat()}


def buy_and_hold(bars, symbols, start, end, capital=100_000.0):
    w = capital / len(symbols)
    return [sum(w * bars[s]["close"][t] / bars[s]["close"][start] for s in symbols) for t in range(start, end)]


# --- metrics -------------------------------------------------------------------------
def returns(equity):
    return [equity[i] / equity[i - 1] - 1 for i in range(1, len(equity))]


def max_drawdown(equity):
    peak, mdd = equity[0], 0.0
    for v in equity:
        peak = max(peak, v)
        mdd = max(mdd, (peak - v) / peak)
    return mdd


def moments(r):
    n = len(r)
    m = sum(r) / n
    var = sum((x - m) ** 2 for x in r) / (n - 1)
    sd = math.sqrt(var)
    if sd == 0:
        return m, 0.0, 0.0, 3.0
    skew = sum((x - m) ** 3 for x in r) / n / sd ** 3
    kurt = sum((x - m) ** 4 for x in r) / n / sd ** 4
    return m, sd, skew, kurt


def metrics(sim_or_equity, trades=None):
    eq = sim_or_equity["equity"] if isinstance(sim_or_equity, dict) else sim_or_equity
    trades = sim_or_equity["trades"] if isinstance(sim_or_equity, dict) else (trades or [])
    r = returns(eq)
    m, sd, skew, kurt = moments(r) if len(r) > 2 else (0.0, 0.0, 0.0, 3.0)
    years = len(r) / 252
    total = eq[-1] / eq[0] - 1
    return {
        "total_return_pct": round(total * 100, 2),
        "cagr_pct": round(((1 + total) ** (1 / years) - 1) * 100, 2) if years > 0 and total > -1 else None,
        "max_drawdown_pct": round(max_drawdown(eq) * 100, 2),
        "sharpe": round(m / sd * math.sqrt(252), 3) if sd > 0 else 0.0,
        "trades": len(trades),
        "win_rate_pct": round(100 * sum(t["pnl"] > 0 for t in trades) / len(trades), 1) if trades else None,
        "days": len(eq),
        "_daily_sr": m / sd if sd > 0 else 0.0, "_skew": skew, "_kurt": kurt,
    }


def deflated_sharpe(daily_sr, n_obs, skew, kurt, n_trials):
    """Bailey & Lopez de Prado (2014). Probability the true Sharpe exceeds the best Sharpe expected
    from n_trials luck-only trials. Sharpe values are per-period (daily), not annualized.
    Assumption: the variance of Sharpe across trials is unknown, so the null-hypothesis estimator
    variance 1/(T-1) is used for it."""
    if n_obs < 3:
        return None
    if n_trials <= 1:
        sr0 = 0.0
    else:
        sd_trials = math.sqrt(1 / (n_obs - 1))
        sr0 = sd_trials * ((1 - EULER_GAMMA) * N01.inv_cdf(1 - 1 / n_trials)
                           + EULER_GAMMA * N01.inv_cdf(1 - 1 / (n_trials * math.e)))
    denom = 1 - skew * daily_sr + (kurt - 1) / 4 * daily_sr ** 2
    if denom <= 0:
        return None
    return N01.cdf((daily_sr - sr0) * math.sqrt(n_obs - 1) / math.sqrt(denom))


# --- test designs ------------------------------------------------------------------------
def walk_forward(strat, bars, k, **kw):
    n = len(next(iter(bars.values()))["dates"])
    edges = [WARMUP + (n - WARMUP) * i // k for i in range(k + 1)]
    out = []
    for a, b in zip(edges, edges[1:]):
        sim = simulate(strat, bars, a, b, **kw)
        bh = buy_and_hold(bars, strat.UNIVERSE, a, b)
        out.append({"start": sim["start"], "end": sim["end"], **public(metrics(sim)),
                    "buy_hold_sharpe": metrics(bh)["sharpe"], "buy_hold_return_pct": metrics(bh)["total_return_pct"]})
    return out


def worst_periods(closes, k, min_start=0):
    """k deepest non-overlapping peak-to-trough drawdowns: [(peak_idx, trough_idx, depth)]."""
    episodes, peak_i, trough_i, depth = [], 0, 0, 0.0
    for i, c in enumerate(closes):
        if c >= closes[peak_i]:
            if depth > 0:
                episodes.append((peak_i, trough_i, depth))
            peak_i, trough_i, depth = i, i, 0.0
        elif (closes[peak_i] - c) / closes[peak_i] > depth:
            trough_i, depth = i, (closes[peak_i] - c) / closes[peak_i]
    if depth > 0:
        episodes.append((peak_i, trough_i, depth))
    # Keep episodes whose trough is tradable; clip the start to the first tradable bar.
    episodes = [(max(p, min_start), t, d) for p, t, d in episodes if t > min_start]
    return sorted(episodes, key=lambda e: -e[2])[:k]


def stress_worst_periods(strat, bars, k, **kw):
    bench = bars[CONFIG["benchmark"]]["close"]
    out = []
    for p, tr, depth in worst_periods(bench, k, min_start=WARMUP):
        sim = simulate(strat, bars, p, tr + 1, **kw)
        bh = buy_and_hold(bars, strat.UNIVERSE, p, tr + 1)
        out.append({"start": sim["start"], "end": sim["end"],
                    "benchmark_drawdown_pct": round(depth * 100, 2), **public(metrics(sim)),
                    "buy_hold_return_pct": metrics(bh)["total_return_pct"]})
    return out


def public(m):
    return {k: v for k, v in m.items() if not k.startswith("_")}


# --- prediction lock ------------------------------------------------------------------------
def check_prediction(strategy_id, bt_dir=BT_DIR):
    pred = Path(bt_dir) / f"{strategy_id}-prediction.md"
    if not pred.exists() or not pred.read_text().strip():
        raise SystemExit(f"Refusing to backtest: write the prediction first in {pred}.")
    digest = hashlib.sha256(pred.read_bytes()).hexdigest()
    lock = pred.with_suffix(".sha256")
    if lock.exists() and lock.read_text().strip() != digest:
        raise SystemExit(f"Refusing to backtest: {pred.name} changed after it was locked.")
    lock.write_text(digest + "\n")
    return pred.read_text(), digest


# --- full run --------------------------------------------------------------------------------
def run(strategy_id, hypothesis_id, conn, data_dir=data_mod.DATA_DIR, bt_dir=BT_DIR, max_pos_frac=None):
    prediction, digest = check_prediction(strategy_id, bt_dir)
    h = next((r for r in ledger.search(conn) if r["id"] == hypothesis_id), None)
    if h is None or Path(h["strategy_file"]).stem != strategy_id:
        raise SystemExit(f"Ledger #{hypothesis_id} is not {strategy_id}.")
    strat = load_strategy(f"strategies/{strategy_id}.py")
    if max_pos_frac is None:
        max_pos_frac = 1.0  # owner-approved: strategy target weights, not the paper-trading cap

    full = data_mod.align({s: data_mod.load_csv(s, data_dir) for s in strat.UNIVERSE})
    dev = data_mod.dev_data(full)
    n = len(dev[strat.UNIVERSE[0]]["dates"])
    if n < WARMUP + 252:
        raise SystemExit(f"Only {n} development bars; need at least {WARMUP + 252}.")
    kw = {"max_pos_frac": max_pos_frac}

    base = simulate(strat, dev, WARMUP, n, **kw)
    bm = metrics(base)
    ledger.record_backtest(conn, hypothesis_id, "pending", h["status"])  # count this variation first
    n_trials = conn.execute("SELECT variations_tried FROM hypotheses WHERE id = ?",
                            (hypothesis_id,)).fetchone()[0]
    dsr = deflated_sharpe(bm["_daily_sr"], bm["days"] - 1, bm["_skew"], bm["_kurt"], n_trials)
    bh_eq = buy_and_hold(dev, strat.UNIVERSE, WARMUP, n)
    spy_eq = buy_and_hold(dev, (CONFIG["benchmark"],), WARMUP, n)

    result = {
        "strategy": strategy_id, "hypothesis_id": hypothesis_id, "run_date": date.today().isoformat(),
        "variation_number": n_trials, "prediction_sha256": digest,
        "data": {"first_date": full[strat.UNIVERSE[0]]["dates"][0].isoformat(),
                 "dev_end": dev[strat.UNIVERSE[0]]["dates"][-1].isoformat(),
                 "sealed_fraction": CONFIG["sealed_fraction"], "sealed_touched": False},
        "assumptions": {**CONFIG, "max_position_frac": max_pos_frac, "fills": "next open",
                        "warmup_bars": WARMUP},
        "development": {**public(bm), "deflated_sharpe": round(dsr, 3) if dsr is not None else None,
                        "open_trades_at_end": base["open_trades"]},
        "baselines": {"equal_weight_buy_hold": public(metrics(bh_eq)), "spy_buy_hold": public(metrics(spy_eq))},
        "walk_forward": walk_forward(strat, dev, CONFIG["walk_forward_windows"], **kw),
        "stress": {
            "costs_2x": public(metrics(simulate(strat, dev, WARMUP, n, cost_mult=2.0, **kw))),
            "fills_delayed_1_day": public(metrics(simulate(strat, dev, WARMUP, n, delay=1, **kw))),
            "worst_periods": stress_worst_periods(strat, dev, CONFIG["worst_periods"], **kw),
        },
    }
    stem = f"{result['run_date']}_{strategy_id}_run{n_trials}"
    (Path(bt_dir) / f"{stem}.json").write_text(json.dumps(result, indent=2))
    (Path(bt_dir) / f"{stem}.md").write_text(report_md(result, prediction))
    ledger.update(conn, hypothesis_id,
                  backtest_result=f"run{n_trials}: Sharpe {bm['sharpe']}, DSR {result['development']['deflated_sharpe']}, "
                                  f"MDD {bm['max_drawdown_pct']}%, see backtests/{stem}.md")
    return result, stem


def run_sealed(strategy_id, hypothesis_id, conn, data_dir=data_mod.DATA_DIR, bt_dir=BT_DIR, max_pos_frac=1.0):
    """The one run on the sealed final period. Same strategy, same costs, same rules; no tuning.
    Does not count as a new variation. Refuses if the sealed period was already used for this idea."""
    prediction, digest = check_prediction(strategy_id, bt_dir)
    h = next((r for r in ledger.search(conn) if r["id"] == hypothesis_id), None)
    if h is None or Path(h["strategy_file"]).stem != strategy_id:
        raise SystemExit(f"Ledger #{hypothesis_id} is not {strategy_id}.")
    if not h["backtest_result"] or h["variations_tried"] < 1:
        raise SystemExit("Run the development backtest before the sealed run.")
    strat = load_strategy(f"strategies/{strategy_id}.py")
    full = data_mod.align({s: data_mod.load_csv(s, data_dir) for s in strat.UNIVERSE})
    if data_mod.split_index(len(full[strat.UNIVERSE[0]]["dates"])) < WARMUP:
        raise SystemExit("Not enough history before the sealed period for indicators.")

    bars, k = data_mod.sealed_data(full, conn, hypothesis_id)  # marks it used from here on
    n = len(bars[strat.UNIVERSE[0]]["dates"])
    kw = {"max_pos_frac": max_pos_frac}
    sim = simulate(strat, bars, k, n, **kw)
    m = metrics(sim)
    bh = metrics(buy_and_hold(bars, strat.UNIVERSE, k, n))
    result = {
        "strategy": strategy_id, "hypothesis_id": hypothesis_id, "run_date": date.today().isoformat(),
        "prediction_sha256": digest, "kind": "sealed",
        "period": {"start": sim["start"], "end": sim["end"], "bars": len(sim["equity"])},
        "assumptions": {**CONFIG, "max_position_frac": max_pos_frac, "fills": "next open"},
        "sealed": {**public(m), "open_trades_at_end": sim["open_trades"],
                   "deflated_sharpe": _round(deflated_sharpe(m["_daily_sr"], m["days"] - 1, m["_skew"],
                                                             m["_kurt"], h["variations_tried"]))},
        "costs_2x": public(metrics(simulate(strat, bars, k, n, cost_mult=2.0, **kw))),
        "equal_weight_buy_hold": public(bh),
        "spy_buy_hold": public(metrics(buy_and_hold(bars, (CONFIG["benchmark"],), k, n))),
    }
    stem = f"{result['run_date']}_{strategy_id}_sealed"
    (Path(bt_dir) / f"{stem}.json").write_text(json.dumps(result, indent=2))
    cols = ["total_return_pct", "cagr_pct", "max_drawdown_pct", "win_rate_pct", "trades", "sharpe"]
    (Path(bt_dir) / f"{stem}.md").write_text(
        f"# Sealed-period run: {strategy_id}\n\n"
        f"- Run: {result['run_date']}, ledger #{hypothesis_id}, used once; no changes since the dev backtest\n"
        f"- Period: {sim['start']} to {sim['end']} ({len(sim['equity'])} bars)\n"
        f"- Deflated Sharpe Ratio: **{result['sealed']['deflated_sharpe']}** (trials: {h['variations_tried']})\n\n"
        + _table([{"case": "strategy (sealed)", **result["sealed"]}, {"case": "costs 2x", **result["costs_2x"]},
                  {"case": "equal-weight buy & hold", **bh}, {"case": "SPY buy & hold", **result["spy_buy_hold"]}],
                 ["case"] + cols)
        + "\n## Comparison against the prediction\n\n_To be written by the reviewer._\n")
    ledger.update(conn, hypothesis_id, sealed_test_result=(
        f"Sharpe {m['sharpe']} vs B&H {bh['sharpe']}, MDD {m['max_drawdown_pct']}% vs {bh['max_drawdown_pct']}%, "
        f"see backtests/{stem}.md"))
    return result, stem


def _round(x):
    return round(x, 3) if x is not None else None


def _table(rows, cols):
    head = "| " + " | ".join(cols) + " |\n|" + "---|" * len(cols) + "\n"
    return head + "".join("| " + " | ".join(str(r.get(c)) for c in cols) + " |\n" for r in rows)


def report_md(r, prediction):
    cols = ["total_return_pct", "max_drawdown_pct", "win_rate_pct", "trades", "sharpe"]
    d = r["development"]
    rows = [{"case": "strategy (dev)", **d},
            {"case": "costs 2x", **r["stress"]["costs_2x"]},
            {"case": "fills +1 day", **r["stress"]["fills_delayed_1_day"]},
            {"case": "equal-weight buy & hold", **r["baselines"]["equal_weight_buy_hold"]},
            {"case": "SPY buy & hold", **r["baselines"]["spy_buy_hold"]}]
    return (
        f"# Backtest: {r['strategy']} (variation {r['variation_number']})\n\n"
        f"- Run: {r['run_date']}, ledger #{r['hypothesis_id']}\n"
        f"- Data: {r['data']['first_date']} to {r['data']['dev_end']} (development only; final "
        f"{r['data']['sealed_fraction']:.0%} sealed, not touched)\n"
        f"- Assumptions: {json.dumps(r['assumptions'])}\n"
        f"- Deflated Sharpe Ratio: **{d['deflated_sharpe']}** (trials counted: {r['variation_number']})\n\n"
        "## Results\n\n" + _table(rows, ["case"] + cols) +
        "\n## Walk-forward\n\n" + _table(r["walk_forward"], ["start", "end"] + cols + ["buy_hold_sharpe"]) +
        "\n## Worst periods (benchmark drawdowns)\n\n" +
        _table(r["stress"]["worst_periods"], ["start", "end", "benchmark_drawdown_pct", "total_return_pct",
                                               "max_drawdown_pct", "trades", "buy_hold_return_pct"]) +
        f"\n## Saved prediction (sha256 {r['prediction_sha256'][:12]}…)\n\n{prediction}\n"
        "\n## Comparison against the prediction\n\n_To be written by the reviewer after reading the numbers above._\n"
    )


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--strategy", required=True, help="e.g. trend_filter_200_v1")
    p.add_argument("--hypothesis", type=int, required=True, help="ledger id")
    p.add_argument("--sealed", action="store_true", help="the ONE run on the sealed period")
    a = p.parse_args()
    with ledger.connect() as conn:
        _, stem = (run_sealed if a.sealed else run)(a.strategy, a.hypothesis, conn)
    print(f"Saved backtests/{stem}.md and .json")


if __name__ == "__main__":
    main()
