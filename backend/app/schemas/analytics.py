from __future__ import annotations

from pydantic import BaseModel


class ObservationsPerDay(BaseModel):
    date: str
    count: int


class StatusBreakdown(BaseModel):
    status: str
    count: int


class QualityRatingBreakdown(BaseModel):
    rating: str
    count: int


class TargetObservationCount(BaseModel):
    target_id: int
    target_name: str
    count: int


class AnalyticsSummary(BaseModel):
    observations_per_day: list[ObservationsPerDay]
    status_breakdown: list[StatusBreakdown]
    image_quality_breakdown: list[QualityRatingBreakdown]
    top_targets: list[TargetObservationCount]
    total_observations: int
    success_rate_pct: float
