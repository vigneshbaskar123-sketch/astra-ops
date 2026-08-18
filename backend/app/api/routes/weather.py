from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.observatory import Observatory
from app.models.weather import WeatherRecord
from app.models.user import User
from app.schemas.weather import WeatherRecordRead
from app.services import alert_service
from app.services.weather_simulator import get_weather_provider

router = APIRouter(prefix="/weather", tags=["weather"])


@router.get("/{observatory_id}/current", response_model=WeatherRecordRead)
def current_weather(observatory_id: int, db: Session = Depends(get_db), _u: User = Depends(get_current_user)) -> WeatherRecord:
    """Generates a fresh simulated reading, persists it, and raises a
    weather alert if it's UNSAFE. See services/weather_simulator.py for
    the safety-state thresholds — this endpoint never claims the reading
    is from a real sensor."""
    if not db.get(Observatory, observatory_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Observatory not found")

    reading = get_weather_provider().read()
    record = WeatherRecord(
        observatory_id=observatory_id,
        recorded_at=reading.recorded_at,
        temperature_c=reading.temperature_c,
        humidity_pct=reading.humidity_pct,
        wind_speed_kph=reading.wind_speed_kph,
        rain=reading.rain,
        cloud_condition=reading.cloud_condition,
        safety_state=reading.safety_state,
        source=reading.source,
    )
    db.add(record)
    db.flush()
    alert_service.check_weather(db, record)
    db.commit()
    db.refresh(record)
    return record


@router.get("/{observatory_id}/history", response_model=list[WeatherRecordRead])
def weather_history(
    observatory_id: int, limit: int = 100, db: Session = Depends(get_db), _u: User = Depends(get_current_user)
) -> list[WeatherRecord]:
    return (
        db.query(WeatherRecord)
        .filter(WeatherRecord.observatory_id == observatory_id)
        .order_by(WeatherRecord.recorded_at.desc())
        .limit(limit)
        .all()
    )
