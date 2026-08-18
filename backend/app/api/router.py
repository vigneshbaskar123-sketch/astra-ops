from __future__ import annotations

from fastapi import APIRouter

from app.api.routes import (
    alerts,
    analytics,
    auth,
    fits,
    image_analysis,
    observations,
    planner,
    reports,
    targets,
    telescope,
    users,
    weather,
)

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(telescope.router)
api_router.include_router(targets.router)
api_router.include_router(planner.router)
api_router.include_router(weather.router)
api_router.include_router(fits.router)
api_router.include_router(image_analysis.router)
api_router.include_router(observations.router)
api_router.include_router(alerts.router)
api_router.include_router(analytics.router)
api_router.include_router(reports.router)
