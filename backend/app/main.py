"""FastAPI entrypoint for the Garmin event-aware dashboard service."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.api.router import api_router
from app.config import get_settings


settings = get_settings()
WEB_DIR = Path(__file__).resolve().parent / "web"

app = FastAPI(
    title="Garmin Event-Aware Dashboard API",
    version="0.1.0",
    description=(
        "Internal-test service for Garmin-backed heart rate, stress, sleep, "
        "event annotations, and insight generation."
    ),
)
app.include_router(api_router, prefix=settings.api_prefix)
app.mount("/app-static", StaticFiles(directory=WEB_DIR), name="app-static")


@app.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    return RedirectResponse(url="/app")


@app.get("/app", include_in_schema=False)
def web_app() -> FileResponse:
    return FileResponse(WEB_DIR / "index.html")


@app.get("/healthz", tags=["system"])
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}
