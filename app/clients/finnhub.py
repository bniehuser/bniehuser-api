from typing import Any

import httpx

from app.core.config import settings

from ._base import make_client, request

BASE_URL = "https://finnhub.io/api/v1"
PROVIDER = "finnhub"


def make() -> httpx.AsyncClient:
    return make_client(BASE_URL)


def _params(extra: dict[str, Any]) -> dict[str, Any]:
    return {"token": settings.FINNHUB_API_KEY, **extra}


async def quote(client: httpx.AsyncClient, symbol: str) -> dict[str, Any]:
    resp = await request(
        client, provider=PROVIDER, method="GET", path="/quote", params=_params({"symbol": symbol})
    )
    return resp.json()


async def profile(client: httpx.AsyncClient, symbol: str) -> dict[str, Any]:
    resp = await request(
        client,
        provider=PROVIDER,
        method="GET",
        path="/stock/profile2",
        params=_params({"symbol": symbol}),
    )
    return resp.json()


async def candles(
    client: httpx.AsyncClient,
    symbol: str,
    resolution: str,
    from_: int,
    to: int,
) -> dict[str, Any]:
    resp = await request(
        client,
        provider=PROVIDER,
        method="GET",
        path="/stock/candle",
        params=_params({"symbol": symbol, "resolution": resolution, "from": from_, "to": to}),
    )
    return resp.json()
