# Prediction: trend_filter_200_v1

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
| Annual return (CAGR) | 5% to 9%, below or near buy & hold |
| Max drawdown | 10% to 20%, clearly smaller than buy & hold |
| Win rate (closed trades) | 25% to 45% (many small whipsaw losses, few large wins) |
| Number of trades | 15 to 40 over the development period |
| Sharpe | 0.4 to 0.8, roughly equal to buy & hold |

**Counts as FAILURE if** (after costs): Sharpe is not higher than buy & hold **and** max drawdown is not at least
25% smaller (relative) than buy & hold; **or** it fails in 3 or more of the 5 walk-forward windows;
**or** under 2x costs Sharpe drops below 0.2.
