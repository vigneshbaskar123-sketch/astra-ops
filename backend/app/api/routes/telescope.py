from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, require_role
from app.models.observatory import Instrument, Observatory, Telescope
from app.models.user import User, UserRole
from app.schemas.observatory import (
    InstrumentCreate,
    InstrumentRead,
    ObservatoryCreate,
    ObservatoryRead,
    TelescopeCreate,
    TelescopeLiveStatus,
    TelescopeRead,
)
from app.services import astronomy as astro
from app.services.telescope_simulator import get_telescope_backend

router = APIRouter(tags=["telescope"])


def _to_live_status(state) -> TelescopeLiveStatus:
    return TelescopeLiveStatus(
        telescope_id=state.telescope_id,
        ra_deg=state.ra_deg,
        dec_deg=state.dec_deg,
        altitude_deg=state.altitude_deg,
        azimuth_deg=state.azimuth_deg,
        tracking=state.tracking,
        slewing=state.slewing,
        dome_state=state.dome_state,
        camera_state=state.camera_state,
        current_target_id=state.current_target_id,
        is_simulated=state.is_simulated,
        as_of=datetime.now(timezone.utc).isoformat(),
    )


def _site_for_telescope(db: Session, telescope_id: int) -> astro.Site:
    telescope = db.get(Telescope, telescope_id)
    if not telescope:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Telescope not found")
    obs = telescope.observatory
    return astro.Site(
        latitude_deg=obs.latitude_deg,
        longitude_deg=obs.longitude_deg,
        elevation_m=obs.elevation_m,
        timezone=obs.timezone,
        name=obs.name,
    )


# --- Observatories ---
@router.get("/observatories", response_model=list[ObservatoryRead])
def list_observatories(db: Session = Depends(get_db), _u: User = Depends(get_current_user)) -> list[Observatory]:
    return db.query(Observatory).order_by(Observatory.name).all()


@router.post("/observatories", response_model=ObservatoryRead, status_code=status.HTTP_201_CREATED)
def create_observatory(
    payload: ObservatoryCreate, db: Session = Depends(get_db), _u: User = Depends(require_role(UserRole.ADMIN))
) -> Observatory:
    obs = Observatory(**payload.model_dump())
    db.add(obs)
    db.commit()
    db.refresh(obs)
    return obs


# --- Telescopes ---
@router.get("/telescope", response_model=list[TelescopeRead])
def list_telescopes(db: Session = Depends(get_db), _u: User = Depends(get_current_user)) -> list[Telescope]:
    return db.query(Telescope).order_by(Telescope.name).all()


@router.post("/telescope", response_model=TelescopeRead, status_code=status.HTTP_201_CREATED)
def create_telescope(
    payload: TelescopeCreate, db: Session = Depends(get_db), _u: User = Depends(require_role(UserRole.ADMIN, UserRole.OPERATOR))
) -> Telescope:
    if not db.get(Observatory, payload.observatory_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Observatory not found")
    telescope = Telescope(**payload.model_dump())
    db.add(telescope)
    db.commit()
    db.refresh(telescope)
    return telescope


@router.get("/telescope/{telescope_id}/status", response_model=TelescopeLiveStatus)
def telescope_status(telescope_id: int, db: Session = Depends(get_db), _u: User = Depends(get_current_user)) -> TelescopeLiveStatus:
    site = _site_for_telescope(db, telescope_id)
    backend = get_telescope_backend(lambda tid: _site_for_telescope(db, tid))
    state = backend.get_status(telescope_id)
    return _to_live_status(state)


@router.post("/telescope/{telescope_id}/slew", response_model=TelescopeLiveStatus)
def telescope_slew(
    telescope_id: int,
    ra_deg: float,
    dec_deg: float,
    target_id: int | None = None,
    db: Session = Depends(get_db),
    _u: User = Depends(require_role(UserRole.ADMIN, UserRole.OPERATOR)),
) -> TelescopeLiveStatus:
    backend = get_telescope_backend(lambda tid: _site_for_telescope(db, tid))
    state = backend.slew_to(telescope_id, ra_deg, dec_deg, target_id)
    return _to_live_status(state)


@router.post("/telescope/{telescope_id}/park", response_model=TelescopeLiveStatus)
def telescope_park(
    telescope_id: int, db: Session = Depends(get_db), _u: User = Depends(require_role(UserRole.ADMIN, UserRole.OPERATOR))
) -> TelescopeLiveStatus:
    backend = get_telescope_backend(lambda tid: _site_for_telescope(db, tid))
    state = backend.park(telescope_id)
    return _to_live_status(state)


@router.post("/telescope/{telescope_id}/dome/{action}", response_model=TelescopeLiveStatus)
def telescope_dome(
    telescope_id: int,
    action: str,
    db: Session = Depends(get_db),
    _u: User = Depends(require_role(UserRole.ADMIN, UserRole.OPERATOR)),
) -> TelescopeLiveStatus:
    if action not in ("open", "close"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="action must be 'open' or 'close'")
    backend = get_telescope_backend(lambda tid: _site_for_telescope(db, tid))
    state = backend.open_dome(telescope_id) if action == "open" else backend.close_dome(telescope_id)
    return _to_live_status(state)


# --- Instruments ---
@router.get("/instruments", response_model=list[InstrumentRead])
def list_instruments(db: Session = Depends(get_db), _u: User = Depends(get_current_user)) -> list[Instrument]:
    return db.query(Instrument).order_by(Instrument.name).all()


@router.post("/instruments", response_model=InstrumentRead, status_code=status.HTTP_201_CREATED)
def create_instrument(
    payload: InstrumentCreate, db: Session = Depends(get_db), _u: User = Depends(require_role(UserRole.ADMIN, UserRole.OPERATOR))
) -> Instrument:
    if not db.get(Telescope, payload.telescope_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Telescope not found")
    instrument = Instrument(**payload.model_dump())
    db.add(instrument)
    db.commit()
    db.refresh(instrument)
    return instrument
