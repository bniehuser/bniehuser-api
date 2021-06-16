import logging
from typing import List, Optional

import spoonacular as sp
from fastapi import APIRouter
from pydantic import BaseModel

from app.core.config import settings

api = sp.API(settings.RAPIDAPI_KEY)
api.api_root = 'https://spoonacular-recipe-food-nutrition-v1.p.rapidapi.com/'
api.session.headers['x-rapidapi-host'] = 'spoonacular-recipe-food-nutrition-v1.p.rapidapi.com'
api.session.headers['x-rapidapi-key'] = settings.RAPIDAPI_KEY

router = APIRouter()
logger = logging.getLogger(__name__)


class Ingredient(BaseModel):
    id: int
    image: str
    name: str
    name_clean: str
    consistency: Optional[str]
    original: str
    original_name: str
    amount: float
    unit: str

    def __init__(self, **kwargs):
        if 'nameClean' in kwargs:
            kwargs['name_clean'] = kwargs['nameClean']
        else:
            kwargs['name_clean'] = kwargs['name']
        kwargs['original_name'] = kwargs['originalName']
        super().__init__(**kwargs)


class InstructionStep(BaseModel):
    number: int
    step: str


class InstructionPhase(BaseModel):
    name: str
    steps: List[InstructionStep]


class RecipeBase(BaseModel):
    id: int
    title: str
    image: str


class RecipeIngredientSearchResult(RecipeBase):
    used_ingredients: List[Ingredient] = []
    unused_ingredients: List[Ingredient] = []
    missed_ingredients: List[Ingredient] = []

    def __init__(self, **kwargs):
        if 'usedIngredients' in kwargs:
            kwargs['used_ingredients'] = kwargs['usedIngredients']
        if 'unusedIngredients' in kwargs:
            kwargs['unused_ingredients'] = kwargs['unusedIngredients']
        if 'missedIngredients' in kwargs:
            kwargs['missed_ingredients'] = kwargs['missedIngredients']
        super().__init__(**kwargs)


class Recipe(RecipeBase):
    ingredients: List[Ingredient] = []
    ready_in_minutes: int
    servings: int
    summary: str
    instructions: str
    full_instructions: List[InstructionPhase] = []
    source_url: str

    def __init__(self, **kwargs):
        if 'extendedIngredients' in kwargs:
            kwargs['ingredients'] = kwargs['extendedIngredients']
        if 'readyInMinutes' in kwargs:
            kwargs['ready_in_minutes'] = kwargs['readyInMinutes']
        if 'analyzedInstructions' in kwargs:
            kwargs['full_instructions'] = kwargs['analyzedInstructions']
        if 'sourceUrl' in kwargs:
            kwargs['source_url'] = kwargs['sourceUrl']
        super().__init__(**kwargs)


@router.get('/random', response_model=Recipe)
async def get_random_recipe():
    response = api.get_random_recipes(number=1).json()
    # return response['recipes'][0]
    return response['recipes'][0]


@router.get('/recipe/{id}', response_model=Recipe)
async def get_recipe(id: str):
    response = api.get_recipe_information(id=id).json()
    return response


@router.get('/search/{ingredients}', response_model=List[RecipeIngredientSearchResult])
async def search(ingredients: str):
    response = api.search_recipes_by_ingredients(ingredients=ingredients, number=10).json()
    for e in response:
        logger.warning(e)
    return response
