"""Configuration centrale de WafaClub (MVP)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _read_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    environment: str
    database_url: str
    auto_seed: bool
    login_max_attempts: int
    login_window_minutes: int
    app_secret: str
    payments_mode: str

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"

    @property
    def is_simulated_payments(self) -> bool:
        return self.payments_mode.lower() == "simulated"


def _default_database_url() -> str:
    sqlite_path = (BASE_DIR / "data" / "wafaclub.db").as_posix()
    return f"sqlite:///{sqlite_path}"


settings = Settings(
    environment=os.getenv("WAFACLUB_ENV", "development"),
    database_url=os.getenv("DATABASE_URL", _default_database_url()),
    auto_seed=_as_bool(os.getenv("WAFACLUB_AUTO_SEED"), True),
    login_max_attempts=_read_int("WAFACLUB_LOGIN_MAX_ATTEMPTS", 5),
    login_window_minutes=_read_int("WAFACLUB_LOGIN_WINDOW_MINUTES", 15),
    app_secret=os.getenv("WAFACLUB_APP_SECRET", "local-demo-only-not-a-production-secret"),
    payments_mode=os.getenv("WAFACLUB_PAYMENTS_MODE", "simulated"),
)

# Constantes métier documentées.
DEFAULT_POINTS_PER_AMOUNT = 10  # 1 point pour 10 MAD dépensés
GIFT_CARD_MIN_AMOUNT = 20
GIFT_CARD_MAX_AMOUNT = 2000
GIFT_CARD_PRESETS = (50, 100, 200, 500)
REWARD_CODE_TTL_DAYS = 30
GIFT_CARD_TTL_DAYS = 365
