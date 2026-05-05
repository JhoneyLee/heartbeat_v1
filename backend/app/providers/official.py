"""Future official Garmin OAuth/API provider."""

from __future__ import annotations

from datetime import date

from app.domain.models import (
    ActivitySummary,
    DailyHeartRateSummary,
    DailySleepSummary,
    DailyStressSummary,
    HeartRateSample,
)
from app.domain.provider import GarminProvider


class OfficialGarminProvider(GarminProvider):
    """Target implementation once Garmin OAuth and APIs are approved."""

    def authenticate(self, *, username: str, secret: str) -> None:
        _ = (username, secret)
        raise NotImplementedError("Replace with OAuth-based account linking.")

    def fetch_daily_heart_rate(
        self,
        *,
        start_date: date,
        end_date: date,
    ) -> tuple[list[DailyHeartRateSummary], list[HeartRateSample]]:
        _ = (start_date, end_date)
        raise NotImplementedError("Use Health API daily heart rate endpoints.")

    def fetch_daily_stress(
        self,
        *,
        start_date: date,
        end_date: date,
    ) -> list[DailyStressSummary]:
        _ = (start_date, end_date)
        raise NotImplementedError("Use Health API stress endpoints.")

    def fetch_daily_sleep(
        self,
        *,
        start_date: date,
        end_date: date,
    ) -> list[DailySleepSummary]:
        _ = (start_date, end_date)
        raise NotImplementedError("Use Health API sleep endpoints.")

    def fetch_activities(
        self,
        *,
        start_date: date,
        end_date: date,
    ) -> list[ActivitySummary]:
        _ = (start_date, end_date)
        raise NotImplementedError("Use Activity API activity listings.")

    def fetch_activity_heart_rate_samples(
        self,
        *,
        activity_id: str,
    ) -> list[HeartRateSample]:
        _ = activity_id
        raise NotImplementedError("Use Activity API details or FIT downloads.")
