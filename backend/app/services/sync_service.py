"""Sync orchestration service."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from datetime import datetime
from itertools import count
from typing import Any

from app.providers.unofficial import UnofficialGarminProvider


_JOB_COUNTER = count(1)
_JOB_LOG: list[dict[str, Any]] = []


@dataclass(slots=True)
class SyncService:
    provider: UnofficialGarminProvider

    def sync_recent(self, *, days: int = 1) -> dict[str, object]:
        job = self._create_job(job_type="incremental_sync")
        try:
            result = self.provider.run_incremental_sync(days=days)
            self._finish_job(job, status="completed", result=result)
        except Exception as exc:
            self._finish_job(job, status="failed", error=str(exc))
            raise
        return job

    def backfill_metrics(self, *, start_date: date, end_date: date) -> dict[str, object]:
        job = self._create_job(job_type="backfill")
        try:
            result = self.provider.run_backfill_sync(start_date=start_date, end_date=end_date)
            self._finish_job(job, status="completed", result=result)
        except Exception as exc:
            self._finish_job(job, status="failed", error=str(exc))
            raise
        return job

    def list_jobs(self) -> list[dict[str, Any]]:
        return list(reversed(_JOB_LOG))

    def _create_job(self, *, job_type: str) -> dict[str, Any]:
        job = {
            "job_id": f"local-{next(_JOB_COUNTER)}",
            "provider": "garmin",
            "job_type": job_type,
            "status": "running",
            "started_at": datetime.now().isoformat(timespec="seconds"),
        }
        _JOB_LOG.append(job)
        return job

    def _finish_job(
        self,
        job: dict[str, Any],
        *,
        status: str,
        result: dict[str, object] | None = None,
        error: str | None = None,
    ) -> None:
        job["status"] = status
        job["finished_at"] = datetime.now().isoformat(timespec="seconds")
        if result is not None:
            job["result"] = result
        if error is not None:
            job["error"] = error
