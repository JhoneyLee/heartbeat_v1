"""Unofficial Garmin provider for internal testing."""

from __future__ import annotations

import subprocess
from datetime import date
from pathlib import Path

from app.domain.models import (
    ActivitySummary,
    DailyHeartRateSummary,
    DailySleepSummary,
    DailyStressSummary,
    HeartRateSample,
)
from app.domain.provider import GarminProvider


class UnofficialGarminProvider(GarminProvider):
    """Back this with python-garminconnect and the current fetch scripts."""

    def __init__(
        self,
        *,
        collector_python_path: Path,
        collector_script_path: Path,
        analyzer_script_path: Path,
        project_root: Path,
    ) -> None:
        self.collector_python_path = collector_python_path
        self.collector_script_path = collector_script_path
        self.analyzer_script_path = analyzer_script_path
        self.project_root = project_root

    def authenticate(self, *, username: str, secret: str) -> None:
        _ = (username, secret)
        raise NotImplementedError("Wire this to python-garminconnect login.")

    def fetch_daily_heart_rate(
        self,
        *,
        start_date: date,
        end_date: date,
    ) -> tuple[list[DailyHeartRateSummary], list[HeartRateSample]]:
        _ = (start_date, end_date)
        raise NotImplementedError("Map Garmin wellness heart rate to normalized models.")

    def fetch_daily_stress(
        self,
        *,
        start_date: date,
        end_date: date,
    ) -> list[DailyStressSummary]:
        _ = (start_date, end_date)
        raise NotImplementedError("Map Garmin stress payloads to normalized models.")

    def fetch_daily_sleep(
        self,
        *,
        start_date: date,
        end_date: date,
    ) -> list[DailySleepSummary]:
        _ = (start_date, end_date)
        raise NotImplementedError("Map Garmin sleep payloads to normalized models.")

    def fetch_activities(
        self,
        *,
        start_date: date,
        end_date: date,
    ) -> list[ActivitySummary]:
        _ = (start_date, end_date)
        raise NotImplementedError("Map Garmin activities to normalized models.")

    def fetch_activity_heart_rate_samples(
        self,
        *,
        activity_id: str,
    ) -> list[HeartRateSample]:
        _ = activity_id
        raise NotImplementedError("Parse FIT/TCX activity heart rate into normalized samples.")

    def run_incremental_sync(self, *, days: int = 1) -> dict[str, object]:
        return self._run_pipeline(["--days", str(days)])

    def run_backfill_sync(self, *, start_date: date, end_date: date) -> dict[str, object]:
        return self._run_pipeline(
            ["--start-date", start_date.isoformat(), "--end-date", end_date.isoformat()]
        )

    def _run_pipeline(self, collector_args: list[str]) -> dict[str, object]:
        if not self.collector_python_path.exists():
            raise FileNotFoundError(
                f"Collector Python not found: {self.collector_python_path}"
            )
        if not self.collector_script_path.exists():
            raise FileNotFoundError(
                f"Collector script not found: {self.collector_script_path}"
            )
        if not self.analyzer_script_path.exists():
            raise FileNotFoundError(
                f"Analyzer script not found: {self.analyzer_script_path}"
            )

        collector_cmd = [
            str(self.collector_python_path),
            str(self.collector_script_path),
            *collector_args,
        ]
        analyze_cmd = [str(self.collector_python_path), str(self.analyzer_script_path)]

        collector = subprocess.run(
            collector_cmd,
            cwd=self.project_root,
            capture_output=True,
            text=True,
            check=False,
        )
        if collector.returncode != 0:
            raise RuntimeError(
                "Garmin collector failed.\n"
                f"stdout:\n{collector.stdout}\n"
                f"stderr:\n{collector.stderr}"
            )

        analyzer = subprocess.run(
            analyze_cmd,
            cwd=self.project_root,
            capture_output=True,
            text=True,
            check=False,
        )
        if analyzer.returncode != 0:
            raise RuntimeError(
                "Dashboard analyzer failed.\n"
                f"stdout:\n{analyzer.stdout}\n"
                f"stderr:\n{analyzer.stderr}"
            )

        return {
            "collector_command": collector_cmd,
            "analyzer_command": analyze_cmd,
            "collector_stdout_tail": collector.stdout.strip().splitlines()[-10:],
            "analyzer_stdout_tail": analyzer.stdout.strip().splitlines()[-10:],
        }
