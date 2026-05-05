"""Normalized internal models used across providers and services."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime


@dataclass(slots=True)
class DailyHeartRateSummary:
    calendar_date: date
    resting_heart_rate: int | None
    min_heart_rate: int | None
    max_heart_rate: int | None
    average_heart_rate: float | None
    sample_count: int


@dataclass(slots=True)
class HeartRateSample:
    timestamp_local: datetime
    bpm: int
    source: str


@dataclass(slots=True)
class DailyStressSummary:
    calendar_date: date
    average_stress: float | None
    max_stress: int | None
    rest_stress_duration_seconds: int | None


@dataclass(slots=True)
class DailySleepSummary:
    sleep_date: date
    sleep_start_local: datetime | None
    sleep_end_local: datetime | None
    total_sleep_seconds: int | None
    deep_sleep_seconds: int | None
    light_sleep_seconds: int | None
    rem_sleep_seconds: int | None
    awake_seconds: int | None
    sleep_score: int | None


@dataclass(slots=True)
class ActivitySummary:
    provider_activity_id: str
    activity_type: str | None
    activity_name: str | None
    calendar_date: date | None
    start_time_local: datetime | None
    duration_seconds: float | None
    distance_meters: float | None
    average_heart_rate: float | None
    max_heart_rate: int | None


@dataclass(slots=True)
class EventRecord:
    title: str
    start_time_local: datetime
    end_time_local: datetime | None
    description: str | None = None
    source: str = "manual"
    valence: str = "neutral"
    intensity: int = 3
    tags: list[str] = field(default_factory=list)
    people: list[str] = field(default_factory=list)
