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
| `config/`     | `.env` (API keys), `risk_limits.yaml`                     | **no** (only `*.example*` files are tracked) |
| `data/`       | Historical prices                                         | **no**  |
| `src/`        | Shared code (`broker.py` is the only Alpaca entry point)  | yes     |

## Setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# Edit config/.env and paste your Alpaca PAPER keys (never commit or print them)
python3 memory/init_ledger.py
```
