"""The only place this project talks to Alpaca. Paper trading only.

Keys are read from config/.env and are never printed, logged, or returned.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

ENV_PATH = Path(__file__).resolve().parents[1] / "config" / ".env"


class LiveTradingRefused(RuntimeError):
    pass


def _load_keys() -> tuple[str, str]:
    load_dotenv(ENV_PATH, override=False)
    key = os.environ.get("ALPACA_API_KEY", "").strip()
    secret = os.environ.get("ALPACA_SECRET_KEY", "").strip()
    if not key or not secret:
        raise RuntimeError(f"Alpaca paper keys missing; fill in {ENV_PATH}")
    # Alpaca live keys start with "AK"; paper keys start with "PK".
    if key.startswith("AK"):
        raise LiveTradingRefused("Live-account key detected. This project is paper-only.")
    return key, secret


def get_trading_client():
    """Return a paper TradingClient. There is deliberately no live option."""
    from alpaca.trading.client import TradingClient

    key, secret = _load_keys()
    client = TradingClient(key, secret, paper=True)
    del key, secret
    return client
