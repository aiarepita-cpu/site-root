# Backtest: trend_filter_200_v1 (variation 1)

- Run: 2026-10-13, ledger #1
- Data: 2016-01-04 to 2023-07-17 (development only; final 30% sealed, not touched)
- Assumptions: {"sealed_fraction": 0.3, "cost_bps_per_side": 2.0, "slippage_bps_per_side": 1.0, "walk_forward_windows": 5, "worst_periods": 5, "benchmark": "SPY", "max_position_frac": 1.0, "fills": "next open", "warmup_bars": 252}
- Deflated Sharpe Ratio: **0.97** (trials counted: 1)

## Results

| case | total_return_pct | max_drawdown_pct | win_rate_pct | trades | sharpe |
|---|---|---|---|---|---|
| strategy (dev) | 76.93 | 20.11 | 28.8 | 73 | 0.754 |
| costs 2x | 74.4 | 20.55 | 27.4 | 73 | 0.736 |
| fills +1 day | 87.32 | 21.11 | 31.7 | 60 | 0.812 |
| equal-weight buy & hold | 138.19 | 33.2 | None | 0 | 0.731 |
| SPY buy & hold | 123.02 | 33.79 | None | 0 | 0.741 |

## Walk-forward

| start | end | total_return_pct | max_drawdown_pct | win_rate_pct | trades | sharpe | buy_hold_sharpe |
|---|---|---|---|---|---|---|---|
| 2017-01-03 | 2018-04-23 | 24.08 | 9.71 | 50.0 | 2 | 1.415 | 1.448 |
| 2018-04-24 | 2019-08-13 | -5.46 | 18.26 | 25.0 | 28 | -0.369 | 0.557 |
| 2019-08-14 | 2020-12-01 | 26.82 | 17.56 | 30.0 | 10 | 1.207 | 1.044 |
| 2020-12-02 | 2022-03-23 | 14.92 | 11.07 | 46.7 | 15 | 0.82 | 0.787 |
| 2022-03-24 | 2023-07-17 | 4.93 | 11.44 | 16.7 | 18 | 0.472 | 0.178 |

## Worst periods (benchmark drawdowns)

| start | end | benchmark_drawdown_pct | total_return_pct | max_drawdown_pct | trades | buy_hold_return_pct |
|---|---|---|---|---|---|---|
| 2020-02-19 | 2020-03-23 | 33.79 | -16.97 | 16.97 | 6 | -34.17 |
| 2022-01-03 | 2022-10-12 | 24.5 | -11.72 | 11.72 | 14 | -27.9 |
| 2018-09-20 | 2018-12-24 | 19.33 | -13.66 | 13.66 | 11 | -22.44 |
| 2018-01-26 | 2018-02-08 | 10.05 | -9.43 | 9.43 | 0 | -9.67 |
| 2020-09-02 | 2020-09-23 | 9.49 | -9.52 | 9.52 | 0 | -10.28 |

## Saved prediction (sha256 9b162b5dc58f…)

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


## Comparison against the prediction

Reviewer: assistant, 2026-10-13. Independent re-implementation (fractional shares, fixed 1/3 sleeves)
matched trades (73) and win rate (28.8%) exactly; return 82.8% vs 76.9% and Sharpe 0.78 vs 0.75 differ only from sizing details.

| Metric | Predicted | Actual (dev, 2017-01 to 2023-07) | Within prediction? |
|---|---|---|---|
| CAGR | 5% to 9%, below or near buy & hold | 9.15% (buy & hold 14.24%) | Just above range; well below buy & hold, as expected |
| Max drawdown | 10% to 20%, clearly smaller than B&H | 20.11% (B&H 33.20%, 39.4% smaller) | Just above range; reduction as expected |
| Win rate | 25% to 45% | 28.8% | Yes |
| Trades | 15 to 40 | 73 | **No: about double (more whipsaw than expected)** |
| Sharpe | 0.4 to 0.8, about equal to B&H | 0.754 (B&H 0.731) | Yes |

Failure rules:
1. Sharpe not higher than B&H **and** drawdown not 25% smaller: Sharpe is higher (0.754 vs 0.731, a negligible gap)
   and drawdown is 39.4% smaller. **Not triggered.**
2. Fails in 3+ of 5 walk-forward windows: the prediction did not define "fail" per window. Reading it as
   "Sharpe below buy & hold": 2 of 5 (2017-18 slightly, 2018-19 clearly negative). Reading it as "negative return": 1 of 5.
   **Not triggered under either reading.**
3. Sharpe below 0.2 under 2x costs: 0.736. **Not triggered.**

Verdict: **passes the development-period test under the pre-registered rules.** The honest summary is that it
matches buy & hold on risk-adjusted return (not better), gives up about 5 points of annual return, and cuts the
worst drawdown by about 40%. It is a risk-reduction tool, not an edge. Delayed fills did not hurt (Sharpe 0.81).
DSR 0.97 only says Sharpe > 0 is likely after 1 trial; it does not say it beats buy & hold.
Next step per the guide: one run on the sealed period (2023-07-18 to 2026-10-12), not yet done.
