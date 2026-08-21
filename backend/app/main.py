import logging
from contextlib import asynccontextmanager
from pathlib import Path

# Reload trigger
from alembic import command
from alembic.config import Config
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.exceptions import ForbiddenError, NotFoundError, ValidationError
from app.ml.train import MODEL_PATH, train
from app.routers import (
    admin,
    analytics,
    appointments,
    auth,
    documents,
    notifications,
    ocr,
    patients,
    predictions,
    reports,
    research,
    search,
    simulations,
    treatment,
    twins,
)
from app.seed import seed

settings = get_settings()
logger = logging.getLogger(__name__)

BACKEND_ROOT = Path(__file__).resolve().parent.parent


def _run_migrations() -> None:
    """Applies pending Alembic revisions on startup so schema changes are
    always tracked, instead of the previous ad-hoc `create_all()`."""
    alembic_cfg = Config(str(BACKEND_ROOT / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(BACKEND_ROOT / "app" / "migrations"))
    command.upgrade(alembic_cfg, "head")


@asynccontextmanager
async def lifespan(app: FastAPI):
    _run_migrations()
    if not MODEL_PATH.exists():
        train()
    db = SessionLocal()
    try:
        seed(db)
    finally:
        db.close()
    yield


app = FastAPI(title="OncoTwin API", version="1.0.0", lifespan=lifespan)


@app.exception_handler(NotFoundError)
def handle_not_found(request: Request, exc: NotFoundError):
    return JSONResponse(status_code=404, content={"detail": str(exc) or "Not found"})


@app.exception_handler(ForbiddenError)
def handle_forbidden(request: Request, exc: ForbiddenError):
    return JSONResponse(status_code=403, content={"detail": str(exc) or "Forbidden"})


@app.exception_handler(ValidationError)
def handle_validation(request: Request, exc: ValidationError):
    return JSONResponse(status_code=400, content={"detail": str(exc) or "Invalid request"})


@app.exception_handler(Exception)
def handle_unexpected(request: Request, exc: Exception):
    """Catch-all so an unhandled error never leaks a driver message, SQL
    fragment or stack trace to the client. The real exception is logged
    server-side with the request path for diagnosis."""
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "An unexpected internal error occurred."},
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for router in (
    auth.router, patients.router, twins.router, predictions.router, simulations.router,
    documents.router, ocr.router, reports.router, appointments.router, treatment.router,
    notifications.router, analytics.router, admin.router, research.router, search.router,
):
    app.include_router(router)


@app.get("/health")
def health():
    return {"status": "ok"}
