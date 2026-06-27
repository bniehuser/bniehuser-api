from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.clients import openfoodfacts
from app.clients._base import with_upstream
from app.clients.pool import get as get_client

router = APIRouter()


class Product(BaseModel):
    barcode: str
    name: str | None = None
    brand: str | None = None
    ingredients: str | None = None
    allergens: str | None = None
    nutriscore: str | None = None
    image_url: str | None = None
    nutriments: dict[str, Any] = {}


@router.get("/barcode/{barcode}", response_model=Product, operation_id="lookupFoodByBarcode")
async def lookup(barcode: str) -> Product:
    client = get_client("openfoodfacts")

    async def fetch() -> Product:
        data = await openfoodfacts.barcode(client, barcode)
        if data.get("status") == 0:
            raise HTTPException(status_code=404, detail="Product not found")
        p = data.get("product", {})
        return Product(
            barcode=barcode,
            name=p.get("product_name") or None,
            brand=p.get("brands") or None,
            ingredients=p.get("ingredients_text") or None,
            allergens=p.get("allergens") or None,
            nutriscore=p.get("nutriscore_grade") or None,
            image_url=p.get("image_url") or None,
            nutriments=p.get("nutriments") or {},
        )

    return await with_upstream(fetch)
