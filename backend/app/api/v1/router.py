"""
v1 router aggregator.

One router per module, per the FastAPI Backend Architecture Blueprint
Section 3's router-per-module convention — this file is the one place that
changes as new modules land.
"""
from fastapi import APIRouter

from app.api.v1.routers.analytics import router as analytics_router
from app.api.v1.routers.auth import router as auth_router
from app.api.v1.routers.auth import users_router
from app.api.v1.routers.clinical import router as clinical_router
from app.api.v1.routers.documents import router as documents_router
from app.api.v1.routers.notifications import router as notifications_router
from app.api.v1.routers.ocr import router as ocr_router
from app.api.v1.routers.predictions import router as predictions_router
from app.api.v1.routers.reports import router as reports_router
from app.api.v1.routers.twins import router as twins_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(users_router)
api_router.include_router(clinical_router)
api_router.include_router(twins_router)
api_router.include_router(predictions_router)
api_router.include_router(documents_router)
api_router.include_router(ocr_router)
api_router.include_router(analytics_router)
api_router.include_router(reports_router)
api_router.include_router(notifications_router)
