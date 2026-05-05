"""Insight and anomaly routes."""

from datetime import date

from fastapi import APIRouter, Query


router = APIRouter()


@router.get("/anomalies")
def list_anomalies(
    metric: str = Query(...),
    start: date = Query(...),
    end: date = Query(...),
) -> dict[str, object]:
    return {
        "metric": metric,
        "range": {"start": start, "end": end},
        "anomalies": [],
    }


@router.get("/change-points")
def list_change_points(
    metric: str = Query(...),
    start: date = Query(...),
    end: date = Query(...),
) -> dict[str, object]:
    return {
        "metric": metric,
        "range": {"start": start, "end": end},
        "change_points": [],
    }


@router.get("/insights")
def list_insights(
    start: date = Query(...),
    end: date = Query(...),
) -> dict[str, object]:
    return {
        "range": {"start": start, "end": end},
        "insights": [],
    }
