"""Event journal routes."""

from datetime import datetime

from fastapi import APIRouter
from pydantic import BaseModel, Field


router = APIRouter()


class EventCreate(BaseModel):
    title: str
    description: str | None = None
    start_time_local: datetime
    end_time_local: datetime | None = None
    valence: str = Field(default="neutral")
    intensity: int = Field(default=3, ge=1, le=5)
    tags: list[str] = Field(default_factory=list)
    people: list[str] = Field(default_factory=list)


@router.post("")
def create_event(payload: EventCreate) -> dict[str, object]:
    return {
        "message": "Event accepted.",
        "event": payload.model_dump(),
        "next_step": "persist event and queue event-impact recomputation",
    }


@router.get("")
def list_events() -> dict[str, list[dict[str, object]]]:
    return {"events": []}
