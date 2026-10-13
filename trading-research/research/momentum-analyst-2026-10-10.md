# Momentum analyst: SPY, QQQ, IWM

- Date: 2026-10-10
- Role: momentum analyst
- Angle: price/volume technicals only (no fundamentals, macro, or news)
- Universe: SPY, QQQ, IWM (daily bars)
- Status: draft (no idea below has been tested)

## Ledger check

Queried `memory/ledger.db` before writing. It holds 0 hypotheses and 0 evidence rows, so nothing has been tested on SPY/QQQ/IWM and there are no failed ideas to avoid.

## Shared test rules (apply to all three ideas)

- Daily OHLCV, adjusted for splits and dividends. `data/` is currently empty, so the data has to be sourced first.
- Split the data before looking at results: an in-sample period to check the logic, and a later out-of-sample period that is touched once. Parameters below are fixed in advance and not tuned.
- Signals use the close of day t; trades fill at the open of day t+1. Charge a per-trade cost (for example 2 bps per side plus slippage) and report results with and without it.
- Baseline for every idea: buy-and-hold of the same ETF(s) over the same period.
- Report CAGR, annualized volatility, Sharpe, max drawdown, number of trades, % time invested.

---

## Idea 1: Absolute trend filter (200-day moving average)

**Idea:** Hold each ETF only while its daily close is above its 200-day simple moving average; otherwise hold cash.

**Why it might work:** Time-series momentum (an asset's own past return predicting its near-term return) is documented across many asset classes in the academic literature (for example Moskowitz, Ooi & Pedersen, 2012). For equity indices, the main expected benefit is avoiding part of long, deep declines, not higher returns. This is an inference from that literature, not a result on this universe.

**Market conditions it needs:** Long, persistent trends, especially extended bear markets that the filter can sidestep. It does poorly in sideways, choppy markets where price keeps crossing the 200-day average (whipsaw), and in sharp V-shaped selloffs that reverse before the signal reacts.

**What would prove it wrong:** On out-of-sample data and after costs, for a majority of the three ETFs, either:
- Sharpe is not higher than buy-and-hold, **and** max drawdown is not at least 25% smaller (relative) than buy-and-hold; or
- results flip sign when the window changes to 150 or 250 days (shows it is fragile to the parameter).

---

## Idea 2: Relative strength rotation among the three ETFs

**Idea:** At each month-end, hold 100% of the ETF with the highest trailing 6-month total return, but only if that return is positive; otherwise hold cash.

**Why it might work:** Relative (cross-sectional) momentum says recent winners keep outperforming for a while. SPY, QQQ and IWM represent different size/style exposures (broad large-cap, tech-heavy large-cap growth, small-cap), and leadership between them has historically come in multi-month spells. The absolute-return check adds the trend filter from Idea 1. Main weakness: only three assets that are highly correlated, so there is little dispersion to exploit, and results may depend on a few periods.

**Market conditions it needs:** Sustained leadership by one segment (for example, months where large-cap growth clearly outruns small caps, or the reverse) with enough return gap between the three to cover switching costs. It fails when leadership flips every month or so.

**What would prove it wrong:** On out-of-sample data and after costs:
- it does not beat a monthly-rebalanced equal-weight portfolio of SPY/QQQ/IWM on Sharpe; or
- removing its single best calendar year makes it underperform equal-weight (shows the result rests on one episode); or
- a 3-month or 12-month lookback gives the opposite conclusion.

---

## Idea 3: Volume-confirmed 20-day breakout

**Idea:** Go long when an ETF closes at a new 20-day high on volume at least 1.5x its 20-day average volume; exit when it closes below its 10-day low.

**Why it might work:** A breakout on unusually high volume may reflect broad participation rather than a drift on thin trading, so it may be more likely to continue. Evidence for volume as a confirmation signal is weaker and more mixed than for price momentum, and for very liquid index ETFs volume may mostly reflect market-wide activity (for example, options expiry or rebalancing days). That makes this the most speculative of the three.

**Market conditions it needs:** Trending markets with clear range breakouts. It needs volume spikes to come from real buying pressure, not mechanical events. It suffers in range-bound markets where breakouts fail quickly.

**What would prove it wrong:** The test has a built-in control. Compare all 20-day-high breakouts split into two groups, high-volume (≥1.5x) and normal-volume. The idea is wrong if, out of sample:
- the average 10-day forward return of high-volume breakouts is not higher than normal-volume breakouts (and the difference is not statistically distinguishable from zero); or
- the full strategy after costs does not beat buy-and-hold on Sharpe.

---

## Open questions and assumptions

- **No data yet:** none of these ideas has been checked against data. Everything above is a hypothesis, and the "why" sections are reasoning from general literature, not evidence on SPY/QQQ/IWM.
- **Thresholds are my choice:** the falsification thresholds (25% drawdown cut, 1.5x volume) are judgment calls set before testing. Change them before any test runs, not after.
- **Ideas overlap:** they are related (Idea 2 includes Idea 1's filter), so their results will be correlated. Treat them as one family when deciding what to promote.
- **Ledger not updated:** these ideas have not been logged to `memory/ledger.db`.
