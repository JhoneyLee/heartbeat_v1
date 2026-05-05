"""Top-level API router."""

from fastapi import APIRouter

from app.api.routes import analysis, connections, dashboard, events, sync


api_router = APIRouter()
api_router.include_router(connections.router, prefix="/connections", tags=["connections"])
api_router.include_router(sync.router, prefix="/sync", tags=["sync"])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
api_router.include_router(events.router, prefix="/events", tags=["events"])
api_router.include_router(analysis.router, prefix="/analysis", tags=["analysis"])
