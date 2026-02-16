"""FastAPI application for the cc-collab web dashboard."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# Directory setup
WEB_DIR = Path(__file__).parent
TEMPLATES_DIR = WEB_DIR / "templates"
STATIC_DIR = WEB_DIR / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    from cc_collab.web.db import init_db

    await init_db()
    yield
    from cc_collab.web.db import close_db

    await close_db()


app = FastAPI(title="cc-collab Dashboard", lifespan=lifespan)

# Mount static files only if the directory exists
if STATIC_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

templates = Jinja2Templates(directory=str(TEMPLATES_DIR)) if TEMPLATES_DIR.is_dir() else None

# Initialize i18n
from cc_collab.web.i18n import setup_jinja2_i18n  # noqa: E402

setup_jinja2_i18n(templates)

# Register route modules
from cc_collab.web.routes import register_routes  # noqa: E402

register_routes(app)
