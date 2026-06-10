from importlib.metadata import PackageNotFoundError, version
from typing import Any

import httpx

from ._base import make_client, request

BASE_URL = "https://world.openfoodfacts.org/api/v2"
PROVIDER = "openfoodfacts"

try:
    _api_version = version("bniehuser-api")
except PackageNotFoundError:
    _api_version = "0.0.0"

USER_AGENT = f"bniehuser-api/{_api_version} (https://bniehuser.com)"


def make() -> httpx.AsyncClient:
    return make_client(BASE_URL, headers={"User-Agent": USER_AGENT})


async def barcode(client: httpx.AsyncClient, code: str) -> dict[str, Any]:
    resp = await request(client, provider=PROVIDER, method="GET", path=f"/product/{code}")
    return resp.json()
