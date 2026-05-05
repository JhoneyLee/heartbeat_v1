"""Small settings layer without additional runtime dependencies."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    api_prefix: str = "/api"
    app_env: str = "development"
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/heartbeat"
    garmin_provider: str = "unofficial"
    garmin_timezone: str = "Asia/Seoul"
    project_root: Path = Path(".")
    legacy_sqlite_path: Path = Path("data/processed/garmin_heart_rate.sqlite3")
    collector_python_path: Path = Path(".venv/bin/python")
    collector_script_path: Path = Path("scripts/fetch_garmin_heart_rate_fine.py")
    analyzer_script_path: Path = Path("scripts/analyze_heart_rate.py")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    project_root = Path(os.getenv("PROJECT_ROOT", Path(__file__).resolve().parents[2])).resolve()
    return Settings(
        api_prefix=os.getenv("API_PREFIX", "/api"),
        app_env=os.getenv("APP_ENV", "development"),
        database_url=os.getenv(
            "DATABASE_URL",
            "postgresql+psycopg://postgres:postgres@localhost:5432/heartbeat",
        ),
        garmin_provider=os.getenv("GARMIN_PROVIDER", "unofficial"),
        garmin_timezone=os.getenv("GARMIN_TIMEZONE", "Asia/Seoul"),
        project_root=project_root,
        legacy_sqlite_path=Path(
            os.getenv(
                "LEGACY_SQLITE_PATH",
                project_root / "data" / "processed" / "garmin_heart_rate.sqlite3",
            )
        ).resolve(),
        collector_python_path=Path(
            os.getenv("COLLECTOR_PYTHON", project_root / ".venv" / "bin" / "python")
        ).resolve(),
        collector_script_path=Path(
            os.getenv(
                "COLLECTOR_SCRIPT_PATH",
                project_root / "scripts" / "fetch_garmin_heart_rate_fine.py",
            )
        ).resolve(),
        analyzer_script_path=Path(
            os.getenv(
                "ANALYZER_SCRIPT_PATH",
                project_root / "scripts" / "analyze_heart_rate.py",
            )
        ).resolve(),
    )
