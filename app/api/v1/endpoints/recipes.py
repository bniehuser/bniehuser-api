from typing import List

import spoonacular as sp
from fastapi import APIRouter
from pydantic import BaseModel

from app.core.config import settings

api = sp.API(settings.RAPIDAPI_KEY)
api.api_root = 'https://spoonacular-recipe-food-nutrition-v1.p.rapidapi.com/'
api.session.headers['x-rapidapi-host'] = 'spoonacular-recipe-food-nutrition-v1.p.rapidapi.com'
api.session.headers['x-rapidapi-key'] = settings.RAPIDAPI_KEY

router = APIRouter()


class Ingredient(BaseModel):
    id: int
    image: str
    name: str
    name_clean: str
    consistency: str
    original: str
    original_name: str
    amount: float
    unit: str

    def __init__(self, **kwargs):
        kwargs['name_clean'] = kwargs['nameClean']
        kwargs['original_name'] = kwargs['originalName']
        super().__init__(**kwargs)


class InstructionStep(BaseModel):
    number: int
    step: str


class InstructionPhase(BaseModel):
    name: str
    steps: List[InstructionStep]


class Recipe(BaseModel):
    id: int
    title: str
    image: str
    ingredients: List[Ingredient]
    ready_in_minutes: int
    servings: int
    summary: str
    instructions: str
    full_instructions: List[InstructionPhase]
    source_url: str

    def __init__(self, **kwargs):
        kwargs['ingredients'] = kwargs['extendedIngredients']
        kwargs['ready_in_minutes'] = kwargs['readyInMinutes']
        kwargs['full_instructions'] = kwargs['analyzedInstructions']
        kwargs['source_url'] = kwargs['sourceUrl']
        super().__init__(**kwargs)


@router.get('/random', response_model=Recipe)
async def get_random_recipe():
    response = api.get_random_recipes(number=1).json()
    # return response['recipes'][0]
    return response['recipes'][0]
