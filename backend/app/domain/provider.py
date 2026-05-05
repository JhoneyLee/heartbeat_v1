"""Provider contract for Garmin integrations."""

from __future__ import annotations

from datetime import date
from typing import Protocol

from app.domain.models import (
    ActivitySummary,
    DailyHeartRateSummary,
    DailySleepSummary,
    DailyStressSummary,
    HeartRateSample,
)


class GarminProvider(Protocol):
    """Swappable contract for unofficial and official Garmin integrations."""

    def authenticate(self, *, username: str, secret: str) -> None: ...

    def fetch_daily_heart_rate(
        self,
        *,
        start_date: date,
        end_date: date,
    ) -> tuple[list[DailyHeartRateSummary], list[HeartRateSample]]: ...

    def fetch_daily_stress(
        self,
        *,
        start_date: date,
        end_date: date,
    ) -> list[DailyStressSummary]: ...

    def fetch_daily_sleep(
        self,
        *,
        start_date: date,
        end_date: date,
    ) -> list[DailySleepSummary]: ...

    def fetch_activities(
        self,
        *,
        start_date: date,
        end_date: date,
    ) -> list[ActivitySummary]: ...

    def fetch_activity_heart_rate_samples(
        self,
        *,
        activity_id: str,
    ) -> list[HeartRateSample]: ...
