"""Web dashboard route registration."""
from __future__ import annotations

from fastapi import FastAPI

from cc_collab.web.routes.dashboard import router as dashboard_router
from cc_collab.web.routes.history import router as history_router
from cc_collab.web.routes.pipeline import router as pipeline_router
from cc_collab.web.routes.tasks import router as tasks_router
from cc_collab.web.routes.webhooks import router as webhooks_router


def register_routes(app: FastAPI) -> None:
    """Register all route modules on the FastAPI application."""
    app.include_router(dashboard_router)
    app.include_router(pipeline_router)
    app.include_router(tasks_router)
    app.include_router(history_router)
    app.include_router(webhooks_router)
