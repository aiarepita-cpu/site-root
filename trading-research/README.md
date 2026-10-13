# Trading research loop (paper trading only)

AI-assisted research loop: idea, then hypothesis, then backtest, then paper trade, then journal and ledger update.
**Paper trading only.** No live-money account is ever connected; `src/broker.py` hard-codes `paper=True` and rejects live keys.

| Folder        | Purpose                                                   | In git? |
|---------------|-----------------------------------------------------------|---------|
| `research/`   | Idea memos (see `TEMPLATE.md`)                            | yes     |
| `strategies/` | One file per strategy version, `<name>_v<N>.py`           | yes     |
| `backtests/`  | Backtest results                                          | yes     |
| `journal/`    | Every paper-trading decision and its reasoning            | yes     |
| `memory/`     | Hypothesis ledger, `ledger.db` (SQLite)                   | yes     |
| `config/`     | `.env` (API keys), `risk.json` (kill-switch limits)       | `.env`: **no**. `risk.json` and `*.example*`: yes |
| `data/`       | Historical prices                                         | **no**  |
| `src/`        | Shared code (`broker.py` is the only Alpaca entry point)  | yes     |

## Setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# Edit config/.env and paste your Alpaca PAPER keys (never commit or print them)
python3 memory/init_ledger.py
```

## The loop (from the guide)

1. **Research**: memos in `research/`. Agents check the ledger first: `python3 memory/ledger.py search --market SPY`.
2. **Code**: `strategies/<name>_v<N>.py` plus boundary tests in `tests/`.
3. **Backtest**: `python3 -m src.fetch_data` (or drop CSVs in `data/`), write `backtests/<strategy>-prediction.md`, then `python3 -m src.backtest --strategy <name>_v<N> --hypothesis <id>`. Final 30% of dates is sealed (`backtests/config.json`); the prediction is hash-locked on first run; walk-forward, 2x costs, delayed fills, 5 worst periods;
   walk-forward, 2x costs, worst periods. Every attempt calls `ledger.record_backtest` (counts variations for the Deflated Sharpe). Cap: 3–5 revisions per idea.
4. **Paper trade**: `python3 -m src.runner`, once per trading day before the open. Trades only ledger ideas with status
   `passed backtest only`/`passed paper` **and** a sealed-test result, one strategy per paper account.
   Every order goes through `risk.check_order` (limits in `config/risk.json`, all values in percent); blocked orders never reach Alpaca.
5. **Post-mortem**: weekly Critic reads `journal/decisions.jsonl` and writes `journal/review-<date>.md` and ledger lessons.
6. **Memory**: `memory/ledger.db`, one `hypotheses` table (see `memory/schema.sql`).

Run all tests: `python3 -m unittest discover -s tests -t .`
