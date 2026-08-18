from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.fits_data import ImageQualityResult
from app.models.observation import ObservationSession, ObservationStatus
from app.models.target import Target
from app.models.user import User
from app.schemas.analytics import (
    AnalyticsSummary,
    ObservationsPerDay,
    QualityRatingBreakdown,
    StatusBreakdown,
    TargetObservationCount,
)

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/summary", response_model=AnalyticsSummary)
def analytics_summary(db: Session = Depends(get_db), _u: User = Depends(get_current_user)) -> AnalyticsSummary:
    per_day_rows = (
        db.query(ObservationSession.observation_date, func.count(ObservationSession.id))
        .group_by(ObservationSession.observation_date)
        .order_by(ObservationSession.observation_date)
        .all()
    )
    per_day = [ObservationsPerDay(date=str(d), count=c) for d, c in per_day_rows]

    status_rows = (
        db.query(ObservationSession.status, func.count(ObservationSession.id)).group_by(ObservationSession.status).all()
    )
    status_breakdown = [StatusBreakdown(status=s.value, count=c) for s, c in status_rows]

    quality_rows = (
        db.query(ImageQualityResult.rating, func.count(ImageQualityResult.id)).group_by(ImageQualityResult.rating).all()
    )
    quality_breakdown = [QualityRatingBreakdown(rating=r.value, count=c) for r, c in quality_rows]

    top_target_rows = (
        db.query(Target.id, Target.name, func.count(ObservationSession.id).label("cnt"))
        .join(ObservationSession, ObservationSession.target_id == Target.id)
        .group_by(Target.id, Target.name)
        .order_by(func.count(ObservationSession.id).desc())
        .limit(10)
        .all()
    )
    top_targets = [TargetObservationCount(target_id=tid, target_name=name, count=cnt) for tid, name, cnt in top_target_rows]

    total = sum(c for _, c in status_rows)
    completed = sum(c for s, c in status_rows if s == ObservationStatus.COMPLETED)
    success_rate = round((completed / total * 100), 1) if total else 0.0

    return AnalyticsSummary(
        observations_per_day=per_day,
        status_breakdown=status_breakdown,
        image_quality_breakdown=quality_breakdown,
        top_targets=top_targets,
        total_observations=total,
        success_rate_pct=success_rate,
    )
