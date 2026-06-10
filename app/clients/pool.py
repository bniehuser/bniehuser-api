import httpx

from . import finnhub, open_meteo, openfoodfacts, spoonacular, themealdb

_clients: dict[str, httpx.AsyncClient] = {}

_FACTORIES = {
    "finnhub": finnhub.make,
    "spoonacular": spoonacular.make,
    "themealdb": themealdb.make,
    "openfoodfacts": openfoodfacts.make,
    "open_meteo": open_meteo.make,
}


async def open_all() -> None:
    for name, factory in _FACTORIES.items():
        _clients[name] = factory()


async def close_all() -> None:
    for client in _clients.values():
        await client.aclose()
    _clients.clear()


def get(name: str) -> httpx.AsyncClient:
    try:
        return _clients[name]
    except KeyError as err:
        raise RuntimeError(
            f"client '{name}' not initialized — open_all() must run in lifespan startup"
        ) from err
