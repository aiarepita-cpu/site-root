# Sealed-period run: trend_filter_200_v1

- Run: 2026-10-13, ledger #1, used once; no changes since the dev backtest
- Period: 2023-07-18 to 2026-10-12 (813 bars)
- Deflated Sharpe Ratio: **0.975** (trials: 1)

| case | total_return_pct | cagr_pct | max_drawdown_pct | win_rate_pct | trades | sharpe |
|---|---|---|---|---|---|---|
| strategy (sealed) | 58.74 | 15.42 | 10.25 | 58.3 | 12 | 1.105 |
| costs 2x | 58.32 | 15.33 | 10.25 | 58.3 | 12 | 1.099 |
| equal-weight buy & hold | 74.18 | 18.79 | 21.61 | None | 0 | 1.076 |
| SPY buy & hold | 78.28 | 19.65 | 18.75 | None | 0 | 1.27 |

## Comparison against the prediction

Reviewer: assistant, 2026-10-13. Prediction file unchanged (hash verified). No code or parameter changes after the dev run.

The prediction's ranges were written for the development period; the sealed period (2023-07 to 2026-10) was a much
stronger market (buy & hold Sharpe 1.08 vs 0.73), so returns and Sharpe above the ranges are expected and not evidence of an edge.

| Metric | Predicted (dev) | Sealed result | Equal-weight B&H |
|---|---|---|---|
| CAGR | 5% to 9% | 15.42% | 18.79% |
| Max drawdown | 10% to 20% | 10.25% (52.6% smaller than B&H) | 21.61% |
| Win rate | 25% to 45% | 58.3% (only 12 trades) | — |
| Trades | 15 to 40 (6.5 years) | 12 (3.2 years) | — |
| Sharpe | 0.4 to 0.8, about equal to B&H | 1.105 | 1.076 |

Failure rules:
1. Sharpe not higher than B&H **and** drawdown not 25% smaller: Sharpe 1.105 vs 1.076 (higher by a negligible margin),
   drawdown 52.6% smaller. **Not triggered.**
2. Walk-forward rule: applies to the development run (passed there); not re-run on the sealed period.
3. Sharpe below 0.2 at 2x costs: 1.099. **Not triggered.**

Verdict: **passes the sealed test.** Same pattern as development: about equal risk-adjusted return to the equal-weight
benchmark, lower return, roughly half the drawdown. Against SPY alone it is worse on Sharpe (1.105 vs 1.27).
The sealed period has now been used for this idea and cannot be used again.
