from __future__ import annotations

from app.models.weather import CloudCondition, WeatherSafety
from app.services.weather_simulator import SimulatedWeatherProvider, classify_safety


def test_classify_safety_all_clear_is_safe():
    result = classify_safety(rain=False, wind_speed_kph=10.0, humidity_pct=50.0, cloud_condition=CloudCondition.CLEAR)
    assert result == WeatherSafety.SAFE


def test_classify_safety_rain_is_always_unsafe():
    result = classify_safety(rain=True, wind_speed_kph=0.0, humidity_pct=10.0, cloud_condition=CloudCondition.CLEAR)
    assert result == WeatherSafety.UNSAFE


def test_classify_safety_high_wind_is_unsafe():
    result = classify_safety(rain=False, wind_speed_kph=45.0, humidity_pct=50.0, cloud_condition=CloudCondition.CLEAR)
    assert result == WeatherSafety.UNSAFE


def test_classify_safety_moderate_wind_is_warning():
    result = classify_safety(rain=False, wind_speed_kph=30.0, humidity_pct=50.0, cloud_condition=CloudCondition.CLEAR)
    assert result == WeatherSafety.WARNING


def test_classify_safety_overcast_is_unsafe_even_without_rain():
    result = classify_safety(rain=False, wind_speed_kph=5.0, humidity_pct=40.0, cloud_condition=CloudCondition.OVERCAST)
    assert result == WeatherSafety.UNSAFE


def test_classify_safety_worst_factor_wins():
    # Wind alone would be WARNING, but overcast alone is UNSAFE -> overall UNSAFE
    result = classify_safety(rain=False, wind_speed_kph=30.0, humidity_pct=40.0, cloud_condition=CloudCondition.OVERCAST)
    assert result == WeatherSafety.UNSAFE


def test_simulated_provider_produces_valid_ranges_and_matches_its_own_classification():
    provider = SimulatedWeatherProvider(seed=7)
    for _ in range(25):
        reading = provider.read()
        assert 0.0 <= reading.humidity_pct <= 100.0
        assert 0.0 <= reading.wind_speed_kph <= 70.0
        expected = classify_safety(
            rain=reading.rain,
            wind_speed_kph=reading.wind_speed_kph,
            humidity_pct=reading.humidity_pct,
            cloud_condition=reading.cloud_condition,
        )
        assert reading.safety_state == expected
