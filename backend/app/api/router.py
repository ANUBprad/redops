"""Root API router. Mounts all endpoint modules."""

from fastapi import APIRouter

from app.agents.api.router import agent_run_router
from app.analytics.api.router import analytics_router
from app.api.agent import agent_router
from app.api.evaluation import evaluation_router
from app.api.evaluation_run import run_router
from app.api.health import health_router
from app.api.metrics import metrics_router
from app.api.observability import observability_router
from app.api.redteam import redteam_router
from app.api.replay import router as replay_router
from app.apikeys.api import apikeys_router
from app.audit.api.router import audit_router
from app.identity.api.router import identity_router
from app.notification.api.router import notification_router
from app.project.api.router import projects_router
from app.scheduling.api import schedules_router
from app.tenant.api.router import tenant_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health_router)
api_router.include_router(identity_router)
api_router.include_router(tenant_router)
api_router.include_router(projects_router)
api_router.include_router(apikeys_router)
api_router.include_router(schedules_router)
api_router.include_router(evaluation_router)
api_router.include_router(run_router)
api_router.include_router(metrics_router)
api_router.include_router(agent_router)
api_router.include_router(agent_run_router)
api_router.include_router(observability_router)
api_router.include_router(redteam_router)
api_router.include_router(analytics_router)
api_router.include_router(audit_router)
api_router.include_router(notification_router)
api_router.include_router(replay_router)
