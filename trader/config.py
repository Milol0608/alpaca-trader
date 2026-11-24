"""Settings and the live-trading lock.

MODE defaults to paper. Live trading needs all three: MODE=live, LIVE_TRADING_CONFIRMED set to the
exact phrase, and a gate file younger than GATE_MAX_AGE_DAYS that records passed=true.
`check_live_gate` reports every failed condition, not just the first.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from enum import StrEnum
from functools import lru_cache
from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

LIVE_CONFIRMATION_PHRASE = "yes-i-understand-real-money"


class Mode(StrEnum):
    PAPER = "paper"
    LIVE = "live"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    mode: Mode = Mode.PAPER
    live_trading_confirmed: str = ""
    gate_file: Path = Path("gate_passed.json")
    gate_max_age_days: int = 30

    alpaca_paper_key_id: str = ""
    alpaca_paper_secret_key: SecretStr = SecretStr("")
    alpaca_live_key_id: str = ""
    alpaca_live_secret_key: SecretStr = SecretStr("")

    # From Alpaca's docs (verified 2026-11-24): separate hosts for paper and live trading; one data host.
    alpaca_paper_url: str = "https://paper-api.alpaca.markets"
    alpaca_live_url: str = "https://api.alpaca.markets"
    alpaca_data_url: str = "https://data.alpaca.markets"
    # Free (Basic) plan: 200 historical data calls/minute. Stay a little under it.
    data_requests_per_minute: int = 180
    # Free plan: IEX is the only feed usable without a subscription (docs). It's one exchange's
    # trades, so volumes are a fraction of the whole market's.
    data_feed: str = "iex"

    data_dir: Path = Path("data")
    etfs_file: Path = Path("data/etfs.json")
    universe_size: int = 500           # most-traded stocks kept each month, plus the ETFs
    universe_min_price: float = 5.0
    universe_lookback_days: int = 60   # trailing window for median dollar volume

    @property
    def trading_url(self) -> str:
        return self.alpaca_live_url if self.mode is Mode.LIVE else self.alpaca_paper_url

    def credentials(self) -> tuple[str, str]:
        """The key pair for the current mode. Paper and live keys are never interchangeable."""
        if self.mode is Mode.LIVE:
            return self.alpaca_live_key_id, self.alpaca_live_secret_key.get_secret_value()
        return self.alpaca_paper_key_id, self.alpaca_paper_secret_key.get_secret_value()


@lru_cache
def get_settings() -> Settings:
    return Settings()


class LiveTradingLocked(RuntimeError):
    """Raised when anything tries to trade real money without passing every gate condition."""


def check_live_gate(settings: Settings, now: datetime | None = None) -> list[str]:
    now = now or datetime.now(timezone.utc)
    failures: list[str] = []
    if settings.mode is not Mode.LIVE:
        failures.append(f"MODE is '{settings.mode}', not 'live'")
    if settings.live_trading_confirmed != LIVE_CONFIRMATION_PHRASE:
        failures.append("LIVE_TRADING_CONFIRMED is not set to the required confirmation phrase")
    failures.extend(_gate_file_failures(settings.gate_file, settings.gate_max_age_days, now))
    return failures


def _gate_file_failures(path: Path, max_age_days: int, now: datetime) -> list[str]:
    # Age comes from the passed_at the gate checker writes, not file mtime (mtime changes on copy).
    if not path.is_file():
        return [f"gate file {path} does not exist"]
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        passed_at = datetime.fromisoformat(data["passed_at"])
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return [f"gate file {path} is unreadable or missing passed_at: {exc}"]
    if data.get("passed") is not True:
        return [f"gate file {path} does not record passed=true"]
    if passed_at.tzinfo is None:
        return [f"gate file {path} passed_at has no timezone"]
    if passed_at > now:
        return [f"gate file {path} passed_at is in the future"]
    if now - passed_at > timedelta(days=max_age_days):
        return [f"gate file {path} is older than {max_age_days} days"]
    return []


def assert_live_allowed(settings: Settings, now: datetime | None = None) -> None:
    failures = check_live_gate(settings, now)
    if failures:
        raise LiveTradingLocked("Live trading is locked: " + "; ".join(failures))
