"""
Quota Guard & Zero-Billing Circuit Breaker.

Tracks monthly API usage in a persistent SQLite database to guarantee that
neither Mapbox nor Google Maps ever exceeds its free monthly tier.
"""
from __future__ import annotations

import os
import sqlite3
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

from utils.logger import setup_logger

load_dotenv()
logger = setup_logger("quota_guard")

_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "api_usage.db"
_DB_PATH.parent.mkdir(parents=True, exist_ok=True)

# Default hard safety caps (90% of free limits to guarantee zero charges)
_DEFAULT_LIMITS = {
    "mapbox": int(os.getenv("MAPBOX_MONTHLY_LIMIT", "90000")),
    "google": int(os.getenv("GOOGLE_MONTHLY_LIMIT", "8500")),
}


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(_DB_PATH), timeout=10.0)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS api_calls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            provider TEXT NOT NULL,
            service TEXT NOT NULL,
            year_month TEXT NOT NULL,
            timestamp TEXT NOT NULL
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_provider_ym ON api_calls (provider, year_month)")
    return conn


class QuotaGuard:
    @staticmethod
    def _current_ym() -> str:
        return datetime.now().strftime("%Y-%m")

    @classmethod
    def get_monthly_count(cls, provider: str, year_month: str | None = None) -> int:
        ym = year_month or cls._current_ym()
        with _get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT COUNT(*) FROM api_calls WHERE provider = ? AND year_month = ?",
                (provider.lower(), ym),
            )
            row = cursor.fetchone()
            return row[0] if row else 0

    @classmethod
    def can_use(cls, provider: str) -> bool:
        provider = provider.lower()
        limit = _DEFAULT_LIMITS.get(provider, 1000)
        current_count = cls.get_monthly_count(provider)
        if current_count >= limit:
            logger.warning(
                f"Quota limit reached for {provider.upper()}: {current_count}/{limit}. "
                "Circuit-breaker engaged to prevent billing."
            )
            return False
        return True

    @classmethod
    def record_call(cls, provider: str, service: str = "routing") -> None:
        ym = cls._current_ym()
        now_iso = datetime.now().isoformat()
        with _get_conn() as conn:
            conn.execute(
                "INSERT INTO api_calls (provider, service, year_month, timestamp) VALUES (?, ?, ?, ?)",
                (provider.lower(), service.lower(), ym, now_iso),
            )
        count = cls.get_monthly_count(provider, ym)
        limit = _DEFAULT_LIMITS.get(provider.lower(), 1000)
        logger.debug(f"Recorded API call to {provider.upper()} ({service}). Monthly usage: {count}/{limit}")

    @classmethod
    def get_usage_summary(cls) -> dict:
        ym = cls._current_ym()
        summary = {}
        for prov, limit in _DEFAULT_LIMITS.items():
            used = cls.get_monthly_count(prov, ym)
            pct = round((used / limit) * 100, 2) if limit > 0 else 0
            summary[prov] = {
                "month": ym,
                "used": used,
                "limit": limit,
                "percent_used": pct,
                "available": max(0, limit - used),
                "is_active": used < limit,
            }
        return summary
