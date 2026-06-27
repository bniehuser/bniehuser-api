from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.clients import open_meteo
from app.clients._base import with_upstream
from app.clients.pool import get as get_client

router = APIRouter()


class CurrentWeather(BaseModel):
    latitude: float
    longitude: float
    timezone: str
    temperature: float
    apparent_temperature: float
    humidity: float
    wind_speed: float
    wind_direction: float
    weather_code: int
    sunrise: str | None = None
    sunset: str | None = None


class DailyForecast(BaseModel):
    date: str
    weather_code: int
    temperature_max: float
    temperature_min: float
    precipitation: float
    sunrise: str
    sunset: str


class Forecast(BaseModel):
    latitude: float
    longitude: float
    timezone: str
    days: list[DailyForecast]


@router.get("/current", response_model=CurrentWeather, operation_id="getCurrentWeather")
async def current(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
) -> CurrentWeather:
    client = get_client("open_meteo")

    async def fetch() -> CurrentWeather:
        data = await open_meteo.current(client, lat, lon)
        cur = data["current"]
        daily = data.get("daily", {})
        sunrises = daily.get("sunrise") or [None]
        sunsets = daily.get("sunset") or [None]
        return CurrentWeather(
            latitude=data["latitude"],
            longitude=data["longitude"],
            timezone=data["timezone"],
            temperature=cur["temperature_2m"],
            apparent_temperature=cur["apparent_temperature"],
            humidity=cur["relative_humidity_2m"],
            wind_speed=cur["wind_speed_10m"],
            wind_direction=cur["wind_direction_10m"],
            weather_code=cur["weather_code"],
            sunrise=sunrises[0],
            sunset=sunsets[0],
        )

    return await with_upstream(fetch)


@router.get("/forecast", response_model=Forecast, operation_id="getWeatherForecast")
async def forecast(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    days: int = Query(7, ge=1, le=16),
) -> Forecast:
    client = get_client("open_meteo")

    async def fetch() -> Forecast:
        data = await open_meteo.forecast(client, lat, lon, days)
        d = data["daily"]
        items = [
            DailyForecast(
                date=d["time"][i],
                weather_code=d["weather_code"][i],
                temperature_max=d["temperature_2m_max"][i],
                temperature_min=d["temperature_2m_min"][i],
                precipitation=d["precipitation_sum"][i],
                sunrise=d["sunrise"][i],
                sunset=d["sunset"][i],
            )
            for i in range(len(d["time"]))
        ]
        return Forecast(
            latitude=data["latitude"],
            longitude=data["longitude"],
            timezone=data["timezone"],
            days=items,
        )

    return await with_upstream(fetch)
