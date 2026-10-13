# Strategies

One file per strategy version: `<name>_v<N>.py` (for example `trend_filter_200_v1.py`).

- Never edit a version after it has been backtested or paper traded; copy it to `_v<N+1>` instead.
- Backtest results in `backtests/` and journal entries in `journal/` refer to `<name>_v<N>`.

## Required structure

Each file is pure Python (no I/O, no broker calls) and contains, in order:

1. Module docstring: one line starting with `Hypothesis:`.
2. `STRATEGY_NAME`, `VERSION`, `HYPOTHESIS`, `MEMO` (link to the research memo), `UNIVERSE`.
3. `PARAMS`: fixed parameters. Changing one means a new version.
4. `RISK`: strategy-level risk (target weight, stop rules). Global caps in `config/risk.json` apply on top.
5. Entry rules: `entry_signal(...)`.
6. Exit rules: `exit_signal(...)`.
7. Position sizing: `position_size(equity, price, max_position_pct)`; returns whole shares. `max_position_pct` is a fraction here (0.10); the runner converts from the percent in `config/risk.json`.

Signals use data up to and including today's close; the caller fills at the next open.

Every strategy needs `tests/test_<name>_v<N>.py` covering each rule at its exact boundary.
Run all tests: `python3 -m unittest discover -s tests -t .`

| Strategy | Hypothesis (memo) |
|---|---|
| `trend_filter_200_v1` | Idea 1, research/momentum-analyst-2026-10-10.md |
| `relative_strength_rotation_v1` | Idea 2, same memo |
| `volume_breakout_v1` | Idea 3, same memo |
