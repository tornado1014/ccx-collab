"""Web dashboard route registration."""
from __future__ import annotations

from fastapi import FastAPI

from ccx_collab.web.routes.cleanup import router as cleanup_router
from ccx_collab.web.routes.config import router as config_router
from ccx_collab.web.routes.dashboard import router as dashboard_router
from ccx_collab.web.routes.health import router as health_router
from ccx_collab.web.routes.history import router as history_router
from ccx_collab.web.routes.logs import router as logs_router
from ccx_collab.web.routes.pipeline import router as pipeline_router
from ccx_collab.web.routes.results import router as results_router
from ccx_collab.web.routes.stages import router as stages_router
from ccx_collab.web.routes.tasks import router as tasks_router
from ccx_collab.web.routes.webhooks import router as webhooks_router


def register_routes(app: FastAPI) -> None:
    """Register all route modules on the FastAPI application."""
    app.include_router(dashboard_router)
    app.include_router(pipeline_router)
    app.include_router(tasks_router)
    app.include_router(history_router)
    app.include_router(stages_router)
    app.include_router(webhooks_router)
    app.include_router(health_router)
    app.include_router(cleanup_router)
    app.include_router(config_router)
    app.include_router(logs_router)
    app.include_router(results_router)
