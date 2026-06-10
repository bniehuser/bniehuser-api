from typing import Any

import httpx

from app.core.config import settings

from ._base import make_client, request

BASE_URL = "https://api.spoonacular.com"
PROVIDER = "spoonacular"


def make() -> httpx.AsyncClient:
    return make_client(BASE_URL)


def _params(extra: dict[str, Any]) -> dict[str, Any]:
    return {"apiKey": settings.SPOONACULAR_API_KEY, **extra}


async def search(client: httpx.AsyncClient, query: str, number: int = 10) -> dict[str, Any]:
    resp = await request(
        client,
        provider=PROVIDER,
        method="GET",
        path="/recipes/complexSearch",
        params=_params({"query": query, "number": number}),
    )
    return resp.json()


async def random_recipe(client: httpx.AsyncClient) -> dict[str, Any]:
    resp = await request(
        client,
        provider=PROVIDER,
        method="GET",
        path="/recipes/random",
        params=_params({"number": 1}),
    )
    return resp.json()


async def recipe_information(client: httpx.AsyncClient, recipe_id: int) -> dict[str, Any]:
    resp = await request(
        client,
        provider=PROVIDER,
        method="GET",
        path=f"/recipes/{recipe_id}/information",
        params=_params({}),
    )
    return resp.json()
