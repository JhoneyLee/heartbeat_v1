"""Sync orchestration routes."""

from datetime import date

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.config import get_settings
from app.providers.unofficial import UnofficialGarminProvider
from app.services.sync_service import SyncService


router = APIRouter()


class SyncNowRequest(BaseModel):
    days: int = Field(default=1, ge=1, le=365)


class BackfillRequest(BaseModel):
    start_date: date
    end_date: date


def _build_sync_service() -> SyncService:
    settings = get_settings()
    provider = UnofficialGarminProvider(
        collector_python_path=settings.collector_python_path,
        collector_script_path=settings.collector_script_path,
        analyzer_script_path=settings.analyzer_script_path,
        project_root=settings.project_root,
    )
    return SyncService(provider=provider)


@router.post("/garmin")
def sync_garmin_now(payload: SyncNowRequest | None = None) -> dict[str, object]:
    service = _build_sync_service()
    try:
        return service.sync_recent(days=payload.days if payload else 1)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/garmin/backfill")
def sync_garmin_backfill(payload: BackfillRequest) -> dict[str, object]:
    if payload.end_date < payload.start_date:
        raise HTTPException(status_code=400, detail="end_date must be on or after start_date")

    service = _build_sync_service()
    try:
        return service.backfill_metrics(
            start_date=payload.start_date,
            end_date=payload.end_date,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/jobs")
def list_sync_jobs() -> dict[str, list[dict[str, object]]]:
    service = _build_sync_service()
    return {"jobs": service.list_jobs()}
