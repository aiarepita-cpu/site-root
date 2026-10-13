# Prediction: relative_strength_rotation_v1

- Written: 2026-10-13, approved by the owner before any backtest.
- Source: research/predictions-draft-2026-10-13.md (draft by the assistant, approved unchanged).
- Locked: this file is hash-locked on the first backtest run and must never be edited.

## Assumptions

- Development period only (first 70% of the data). Costs 2 bps + 1 bp slippage per side, fills at next open.
- **Sizing for the backtest: each strategy's own target weights** (1/3 per ETF for trend filter and breakout,
  100% in one ETF for rotation), not the 10% paper-trading cap from `config/risk.json`.
  Reason: with a 10% cap the returns and drawdowns shrink by roughly 3–10x and stop being comparable to buy & hold.
  Sharpe and win rate barely change with sizing, so paper results remain comparable on those two.
- Benchmark: equal-weight SPY/QQQ/IWM buy & hold over the same period.

## Prediction

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
