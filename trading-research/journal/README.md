# Paper-trading journal

One entry for every paper-trading decision, including the decision not to trade.
Written by `src/journal.py`: `YYYY-MM-DD.md` per day for reading, `decisions.jsonl` for the Critic. Each entry records:

- Time (UTC), strategy and version, hypothesis ID
- Decision (buy / sell / hold / skip), symbol, qty, order type
- Reasoning and the signals used
- Risk check result (which limits were checked, pass/fail)
- Alpaca order ID (paper) and outcome, filled in later
