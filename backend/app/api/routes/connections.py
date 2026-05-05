"""Connection management routes."""

from fastapi import APIRouter
from pydantic import BaseModel


router = APIRouter()


class GarminConnectionCreate(BaseModel):
    garmin_email: str
    garmin_password: str


@router.post("/garmin")
def create_garmin_connection(payload: GarminConnectionCreate) -> dict[str, object]:
    return {
        "message": "Connection request accepted.",
        "auth_type": "unofficial",
        "garmin_email": payload.garmin_email,
        "next_step": "persist encrypted credentials and enqueue initial backfill",
    }


@router.get("")
def list_connections() -> dict[str, list[dict[str, str]]]:
    return {
        "connections": [
            {
                "provider": "garmin",
                "auth_type": "unofficial",
                "status": "design-scaffold",
            }
        ]
    }
