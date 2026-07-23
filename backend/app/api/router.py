"""Root API router. Mounts only health endpoints."""

from fastapi import APIRouter

from app.api.health import health_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health_router)
