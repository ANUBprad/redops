"""Root API router. Mounts all endpoint modules."""

from fastapi import APIRouter

from app.analytics.api.router import analytics_router
from app.api.agent import agent_router
from app.api.evaluation import evaluation_router
from app.api.evaluation_run import run_router
from app.api.health import health_router
from app.api.metrics import metrics_router
from app.api.observability import observability_router
from app.api.redteam import redteam_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health_router)
api_router.include_router(evaluation_router)
api_router.include_router(run_router)
api_router.include_router(metrics_router)
api_router.include_router(agent_router)
api_router.include_router(observability_router)
api_router.include_router(redteam_router)
api_router.include_router(analytics_router)
