from typing import Any, Literal

import structlog
from fastapi import APIRouter
from pydantic import BaseModel

from app.clients import spoonacular, themealdb
from app.clients._base import UpstreamError
from app.clients.pool import get as get_client

log = structlog.get_logger()
router = APIRouter()


class Recipe(BaseModel):
    id: str
    title: str
    image: str | None = None
    source: Literal["spoonacular", "themealdb"]


class RecipeSearchResponse(BaseModel):
    query: str
    results: list[Recipe]
    sources: list[str]
    partial: bool = False


def _spoon_to_recipe(item: dict[str, Any]) -> Recipe:
    return Recipe(
        id=str(item["id"]),
        title=item["title"],
        image=item.get("image"),
        source="spoonacular",
    )


def _meal_to_recipe(item: dict[str, Any]) -> Recipe:
    return Recipe(
        id=str(item["idMeal"]),
        title=item["strMeal"],
        image=item.get("strMealThumb"),
        source="themealdb",
    )


@router.get("/search", response_model=RecipeSearchResponse)
async def search(q: str, number: int = 10) -> RecipeSearchResponse:
    spoon_client = get_client("spoonacular")
    meal_client = get_client("themealdb")
    sources: list[str] = []
    partial = False
    results: list[Recipe] = []

    try:
        spoon = await spoonacular.search(spoon_client, q, number=number)
        results.extend(_spoon_to_recipe(item) for item in spoon.get("results", []))
        sources.append("spoonacular")
    except UpstreamError as err:
        log.warning("spoonacular_unavailable", code=err.code, status=err.status)
        partial = True

    try:
        meal = await themealdb.search(meal_client, q)
        meal_items = meal.get("meals") or []
        results.extend(_meal_to_recipe(item) for item in meal_items)
        sources.append("themealdb")
    except UpstreamError as err:
        log.warning("themealdb_unavailable", code=err.code, status=err.status)
        partial = True

    return RecipeSearchResponse(query=q, results=results, sources=sources, partial=partial)
