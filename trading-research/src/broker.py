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


def assert_paper(client) -> None:
    """Refuse any trading client not pointed at Alpaca's paper endpoint."""
    from alpaca.common.enums import BaseURL

    if getattr(client, "_base_url", None) != BaseURL.TRADING_PAPER:
        raise LiveTradingRefused("Trading client is not on the paper endpoint.")


def get_trading_client():
    """Return a paper TradingClient. There is deliberately no live option or URL override."""
    from alpaca.trading.client import TradingClient

    key, secret = _load_keys()
    client = TradingClient(key, secret, paper=True)
    del key, secret
    assert_paper(client)
    return client


def get_data_client():
    from alpaca.data.historical import StockHistoricalDataClient

    key, secret = _load_keys()
    client = StockHistoricalDataClient(key, secret)
    del key, secret
    return client
