"""Dashboard read routes."""

from datetime import date

from fastapi import APIRouter, HTTPException, Query

from app.config import get_settings
from app.repositories.legacy_sqlite import (
    load_activities,
    load_activity_samples,
    load_daily_heart_rate,
    load_daily_sleep,
    load_daily_stress,
    load_hourly_profile,
    load_overview,
)


router = APIRouter()


def _validate_range(start: date, end: date) -> None:
    if end < start:
        raise HTTPException(status_code=400, detail="end must be on or after start")


@router.get("/overview")
def dashboard_overview(
    start: date = Query(...),
    end: date = Query(...),
) -> dict[str, object]:
    _validate_range(start, end)
    settings = get_settings()
    return {
        "range": {"start": start, "end": end},
        "summary": load_overview(settings.legacy_sqlite_path, start, end),
        "note": "events, anomalies, and change-point layers are still pending in the local SQLite pipeline",
    }


@router.get("/heart-rate/daily")
def daily_heart_rate(
    start: date = Query(...),
    end: date = Query(...),
) -> dict[str, object]:
    _validate_range(start, end)
    settings = get_settings()
    return {
        "range": {"start": start, "end": end},
        "days": load_daily_heart_rate(settings.legacy_sqlite_path, start, end),
    }


@router.get("/heart-rate/hourly")
def hourly_profile(
    start: date = Query(...),
    end: date = Query(...),
) -> dict[str, object]:
    _validate_range(start, end)
    settings = get_settings()
    return {
        "range": {"start": start, "end": end},
        "hours": load_hourly_profile(settings.legacy_sqlite_path, start, end),
    }


@router.get("/stress/daily")
def daily_stress(
    start: date = Query(...),
    end: date = Query(...),
) -> dict[str, object]:
    _validate_range(start, end)
    settings = get_settings()
    return {
        "range": {"start": start, "end": end},
        "days": load_daily_stress(settings.legacy_sqlite_path, start, end),
    }


@router.get("/sleep/daily")
def daily_sleep(
    start: date = Query(...),
    end: date = Query(...),
) -> dict[str, object]:
    _validate_range(start, end)
    settings = get_settings()
    return {
        "range": {"start": start, "end": end},
        "days": load_daily_sleep(settings.legacy_sqlite_path, start, end),
    }


@router.get("/timeline")
def timeline(
    start: date = Query(...),
    end: date = Query(...),
) -> dict[str, object]:
    _validate_range(start, end)
    settings = get_settings()
    return {
        "range": {"start": start, "end": end},
        "series": {
            "daily_heart_rate": load_daily_heart_rate(settings.legacy_sqlite_path, start, end),
            "hourly_profile": load_hourly_profile(settings.legacy_sqlite_path, start, end),
            "activities": load_activities(settings.legacy_sqlite_path, start, end),
            "stress": load_daily_stress(settings.legacy_sqlite_path, start, end),
            "sleep": load_daily_sleep(settings.legacy_sqlite_path, start, end),
            "events": [],
            "anomalies": [],
            "change_points": [],
        },
    }


@router.get("/activities")
def list_activities(
    start: date = Query(...),
    end: date = Query(...),
) -> dict[str, object]:
    _validate_range(start, end)
    settings = get_settings()
    return {
        "range": {"start": start, "end": end},
        "activities": load_activities(settings.legacy_sqlite_path, start, end),
    }


@router.get("/activities/{activity_id}/heart-rate")
def activity_heart_rate(activity_id: int) -> dict[str, object]:
    settings = get_settings()
    samples = load_activity_samples(settings.legacy_sqlite_path, activity_id)
    if not samples:
        raise HTTPException(status_code=404, detail="Activity heart rate samples not found")
    return {
        "activity_id": activity_id,
        "samples": samples,
    }
