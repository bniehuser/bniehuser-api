from typing import Any

import httpx

from app.core.config import settings

from ._base import make_client, request

BASE_URL = "https://api.twelvedata.com"
PROVIDER = "twelvedata"


def make() -> httpx.AsyncClient:
    return make_client(BASE_URL)


def _params(extra: dict[str, Any]) -> dict[str, Any]:
    return {"apikey": settings.TWELVEDATA_API_KEY, **extra}


async def time_series(
    client: httpx.AsyncClient,
    symbol: str,
    interval: str,
    outputsize: int,
) -> dict[str, Any]:
    resp = await request(
        client,
        provider=PROVIDER,
        method="GET",
        path="/time_series",
        params=_params({"symbol": symbol, "interval": interval, "outputsize": outputsize}),
    )
    return resp.json()
