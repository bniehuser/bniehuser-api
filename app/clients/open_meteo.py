from typing import Any

import httpx

from ._base import make_client, request

BASE_URL = "https://api.open-meteo.com/v1"
PROVIDER = "open_meteo"


def make() -> httpx.AsyncClient:
    return make_client(BASE_URL)


async def current(client: httpx.AsyncClient, lat: float, lon: float) -> dict[str, Any]:
    resp = await request(
        client,
        provider=PROVIDER,
        method="GET",
        path="/forecast",
        params={
            "latitude": lat,
            "longitude": lon,
            "current": (
                "temperature_2m,apparent_temperature,relative_humidity_2m,"
                "wind_speed_10m,wind_direction_10m,weather_code"
            ),
            "daily": "sunrise,sunset",
            "timezone": "auto",
            "forecast_days": 1,
        },
    )
    return resp.json()


async def forecast(client: httpx.AsyncClient, lat: float, lon: float, days: int) -> dict[str, Any]:
    resp = await request(
        client,
        provider=PROVIDER,
        method="GET",
        path="/forecast",
        params={
            "latitude": lat,
            "longitude": lon,
            "daily": (
                "weather_code,temperature_2m_max,temperature_2m_min,"
                "precipitation_sum,sunrise,sunset"
            ),
            "timezone": "auto",
            "forecast_days": days,
        },
    )
    return resp.json()
