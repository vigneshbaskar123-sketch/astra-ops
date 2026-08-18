from __future__ import annotations

from datetime import date as date_type

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.observatory import Observatory
from app.models.target import Target
from app.models.user import User
from app.schemas.astronomy import VisibilityReport
from app.services import astronomy as astro

router = APIRouter(prefix="/planner", tags=["planner"])


@router.get("/visibility/{target_id}", response_model=VisibilityReport)
def target_visibility(
    target_id: int,
    observatory_id: int,
    on_date: date_type = Query(..., description="Local calendar date of the observing night"),
    min_altitude_deg: float = Query(30.0, ge=0, le=90),
    db: Session = Depends(get_db),
    _u: User = Depends(get_current_user),
) -> VisibilityReport:
    target = db.get(Target, target_id)
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target not found")
    observatory = db.get(Observatory, observatory_id)
    if not observatory:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Observatory not found")

    site = astro.Site(
        latitude_deg=observatory.latitude_deg,
        longitude_deg=observatory.longitude_deg,
        elevation_m=observatory.elevation_m,
        timezone=observatory.timezone,
        name=observatory.name,
    )
    report = astro.build_visibility_report(
        site=site,
        target_id=target.id,
        target_name=target.name,
        observatory_id=observatory.id,
        ra_deg=target.ra_deg,
        dec_deg=target.dec_deg,
        on_date=on_date,
        min_altitude_deg=min_altitude_deg,
    )
    return VisibilityReport(**report)


@router.get("/currently-visible", response_model=list[VisibilityReport])
def currently_visible_targets(
    observatory_id: int,
    min_altitude_deg: float = Query(30.0, ge=0, le=90),
    db: Session = Depends(get_db),
    _u: User = Depends(get_current_user),
) -> list[VisibilityReport]:
    """Used by both the dashboard and the AI assistant (later stage) to
    answer "what's visible right now" from real, freshly computed
    altitudes — never a cached or guessed list."""
    observatory = db.get(Observatory, observatory_id)
    if not observatory:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Observatory not found")

    site = astro.Site(
        latitude_deg=observatory.latitude_deg,
        longitude_deg=observatory.longitude_deg,
        elevation_m=observatory.elevation_m,
        timezone=observatory.timezone,
        name=observatory.name,
    )

    today = date_type.today()
    results = []
    for target in db.query(Target).all():
        alt, az = astro.current_altaz(site, target.ra_deg, target.dec_deg)
        if alt >= min_altitude_deg:
            report = astro.build_visibility_report(
                site=site, target_id=target.id, target_name=target.name, observatory_id=observatory.id,
                ra_deg=target.ra_deg, dec_deg=target.dec_deg, on_date=today, min_altitude_deg=min_altitude_deg,
            )
            results.append(VisibilityReport(**report))
    return results
