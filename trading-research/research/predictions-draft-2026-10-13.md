# DRAFT predictions (not locked)

Status: **APPROVED by the owner on 2026-10-13, unchanged.** Copied to `backtests/<strategy>-prediction.md`.
On approval, each section is copied to `backtests/<strategy>-prediction.md` and hash-locked on the first backtest run.

Basis: reasoning from `research/momentum-analyst-2026-10-10.md` and general knowledge of trend-following on US index ETFs.
No data has been seen. The data period is not yet known (Alpaca's daily history may start around 2016; unverified).

## Shared assumptions (apply to all three)

- Development period only (first 70% of the data). Costs 2 bps + 1 bp slippage per side, fills at next open.
- **Sizing for the backtest: each strategy's own target weights** (1/3 per ETF for trend filter and breakout,
  100% in one ETF for rotation), not the 10% paper-trading cap from `config/risk.json`.
  Reason: with a 10% cap the returns and drawdowns shrink by roughly 3–10x and stop being comparable to buy & hold.
  Sharpe and win rate barely change with sizing, so paper results remain comparable on those two.
- Benchmark: equal-weight SPY/QQQ/IWM buy & hold over the same period.

---

## trend_filter_200_v1

| Metric | Prediction |
|---|---|
| Annual return (CAGR) | 5% to 9%, below or near buy & hold |
| Max drawdown | 10% to 20%, clearly smaller than buy & hold |
| Win rate (closed trades) | 25% to 45% (many small whipsaw losses, few large wins) |
| Number of trades | 15 to 40 over the development period |
| Sharpe | 0.4 to 0.8, roughly equal to buy & hold |

**Counts as FAILURE if** (after costs): Sharpe is not higher than buy & hold **and** max drawdown is not at least
25% smaller (relative) than buy & hold; **or** it fails in 3 or more of the 5 walk-forward windows;
**or** under 2x costs Sharpe drops below 0.2.

## relative_strength_rotation_v1

| Metric | Prediction |
|---|---|
| Annual return (CAGR) | 6% to 12% |
| Max drawdown | 15% to 30% |
| Win rate (closed trades) | 45% to 60% |
| Number of trades | 15 to 35 over the development period |
| Sharpe | 0.4 to 0.8 |

**Counts as FAILURE if** (after costs): Sharpe is not higher than equal-weight buy & hold; **or** it loses to
equal-weight in 3 or more of the 5 walk-forward windows; **or** its result depends on a single year
(removing the best calendar year makes it lose to equal-weight).

## volume_breakout_v1

| Metric | Prediction |
|---|---|
| Annual return (CAGR) | 2% to 6% (low time in market) |
| Max drawdown | 8% to 15% |
| Win rate (closed trades) | 35% to 50% |
| Number of trades | 30 to 80 over the development period |
| Sharpe | 0.2 to 0.6, below buy & hold |

**Counts as FAILURE if** (after costs): high-volume breakouts do not have higher average 10-day forward returns
than normal-volume breakouts; **or** Sharpe is not higher than buy & hold.

---

## Open items before locking

1. Owner to change any number or failure rule above.
2. Confirm the sizing assumption (target weights, not the 10% cap).
3. The "remove best year" check (rotation) and the "high vs normal volume breakouts" comparison (breakout)
   are not yet computed by `src/backtest.py`; they need to be added before those two can be judged.
