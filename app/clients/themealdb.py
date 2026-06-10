from typing import Any

import httpx

from ._base import make_client, request

BASE_URL = "https://www.themealdb.com/api/json/v1/1"
PROVIDER = "themealdb"


def make() -> httpx.AsyncClient:
    return make_client(BASE_URL)


async def search(client: httpx.AsyncClient, query: str) -> dict[str, Any]:
    resp = await request(
        client, provider=PROVIDER, method="GET", path="/search.php", params={"s": query}
    )
    return resp.json()


async def lookup(client: httpx.AsyncClient, meal_id: str) -> dict[str, Any]:
    resp = await request(
        client, provider=PROVIDER, method="GET", path="/lookup.php", params={"i": meal_id}
    )
    return resp.json()
