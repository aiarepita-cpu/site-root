# Prediction: volume_breakout_v1

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
| Annual return (CAGR) | 2% to 6% (low time in market) |
| Max drawdown | 8% to 15% |
| Win rate (closed trades) | 35% to 50% |
| Number of trades | 30 to 80 over the development period |
| Sharpe | 0.2 to 0.6, below buy & hold |

**Counts as FAILURE if** (after costs): high-volume breakouts do not have higher average 10-day forward returns
than normal-volume breakouts; **or** Sharpe is not higher than buy & hold.
