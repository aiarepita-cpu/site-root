# Strategies

One file per strategy version: `<name>_v<N>.py` (for example `mean_reversion_v1.py`).

- Never edit a version after it has been backtested or paper traded; copy it to `_v<N+1>` instead.
- Each file defines `STRATEGY_NAME` and `VERSION` at the top, matching the filename.
- Backtest results in `backtests/` and journal entries in `journal/` refer to `<name>_v<N>`.
