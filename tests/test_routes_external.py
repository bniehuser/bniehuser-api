import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_stocks_quote(client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_quote(_c, _symbol: str) -> dict:
        return {
            "c": 195.5,
            "d": 1.2,
            "dp": 0.62,
            "h": 196.0,
            "l": 194.0,
            "o": 194.5,
            "pc": 194.3,
            "t": 1700000000,
        }

    async def fake_profile(_c, _symbol: str) -> dict:
        return {
            "ticker": "AAPL",
            "name": "Apple Inc.",
            "exchange": "NASDAQ",
            "finnhubIndustry": "Technology",
            "logo": "https://example.com/aapl.png",
            "currency": "USD",
        }

    monkeypatch.setattr("app.api.v1.endpoints.stocks.finnhub.quote", fake_quote)
    monkeypatch.setattr("app.api.v1.endpoints.stocks.finnhub.profile", fake_profile)

    resp = await client.get("/api/v1/stocks/aapl")
    assert resp.status_code == 200
    body = resp.json()
    assert body["symbol"] == "AAPL"
    assert body["name"] == "Apple Inc."
    assert body["price"] == 195.5
    assert body["change_percent"] == 0.62


async def test_stocks_quote_upstream_error_becomes_502(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.clients._base import UpstreamError

    async def boom(*_a, **_kw):
        raise UpstreamError(provider="finnhub", status=503, code="upstream_5xx", message="oops")

    monkeypatch.setattr("app.api.v1.endpoints.stocks.finnhub.quote", boom)
    resp = await client.get("/api/v1/stocks/aapl")
    assert resp.status_code == 502
    body = resp.json()
    assert body["detail"]["upstream"] == "finnhub"


async def test_stocks_history_ascending(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fake_time_series(_c, _symbol: str, _interval: str, _outputsize: int) -> dict:
        return {
            "meta": {"symbol": "AAPL", "interval": "1day"},
            "values": [
                {
                    "datetime": "2026-06-12",
                    "open": "197.0",
                    "high": "199.0",
                    "low": "196.0",
                    "close": "198.5",
                    "volume": "50000000",
                },
                {
                    "datetime": "2026-06-11",
                    "open": "195.0",
                    "high": "197.0",
                    "low": "194.0",
                    "close": "196.0",
                    "volume": "42000000",
                },
            ],
        }

    monkeypatch.setattr("app.api.v1.endpoints.stocks.twelvedata.time_series", fake_time_series)
    resp = await client.get("/api/v1/stocks/aapl/history")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 2
    # reversed to ascending date order
    assert body[0]["date"] == "2026-06-11"
    assert body[1]["date"] == "2026-06-12"
    assert body[1]["close"] == 198.5
    assert body[0]["volume"] == 42000000


async def test_stocks_history_upstream_error_becomes_502(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.clients._base import UpstreamError

    async def boom(*_a, **_kw):
        raise UpstreamError(provider="twelvedata", status=429, code="upstream_4xx", message="rate")

    monkeypatch.setattr("app.api.v1.endpoints.stocks.twelvedata.time_series", boom)
    resp = await client.get("/api/v1/stocks/aapl/history")
    assert resp.status_code == 502
    assert resp.json()["detail"]["upstream"] == "twelvedata"


async def test_recipes_search_merges_sources(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fake_spoon(_c, _q: str, number: int = 10) -> dict:
        return {"results": [{"id": 1, "title": "Pizza", "image": "https://x/p.jpg"}]}

    async def fake_meal(_c, _q: str) -> dict:
        return {
            "meals": [
                {"idMeal": "52", "strMeal": "Pizza Marinara", "strMealThumb": "https://x/m.jpg"}
            ]
        }

    monkeypatch.setattr("app.api.v1.endpoints.recipes.spoonacular.search", fake_spoon)
    monkeypatch.setattr("app.api.v1.endpoints.recipes.themealdb.search", fake_meal)

    resp = await client.get("/api/v1/recipes/search?q=pizza")
    assert resp.status_code == 200
    body = resp.json()
    assert body["sources"] == ["spoonacular", "themealdb"]
    assert body["partial"] is False
    assert len(body["results"]) == 2


async def test_recipes_search_partial_when_spoonacular_down(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.clients._base import UpstreamError

    async def boom(*_a, **_kw):
        raise UpstreamError(
            provider="spoonacular", status=402, code="upstream_4xx", message="quota"
        )

    async def fake_meal(_c, _q: str) -> dict:
        return {
            "meals": [{"idMeal": "52", "strMeal": "Biryani", "strMealThumb": "https://x/m.jpg"}]
        }

    monkeypatch.setattr("app.api.v1.endpoints.recipes.spoonacular.search", boom)
    monkeypatch.setattr("app.api.v1.endpoints.recipes.themealdb.search", fake_meal)

    resp = await client.get("/api/v1/recipes/search?q=biryani")
    assert resp.status_code == 200
    body = resp.json()
    assert body["partial"] is True
    assert body["sources"] == ["themealdb"]
    assert len(body["results"]) == 1


async def test_food_barcode_ok(client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_barcode(_c, _code: str) -> dict:
        return {
            "status": 1,
            "product": {
                "product_name": "Nutella",
                "brands": "Ferrero",
                "ingredients_text": "sugar, palm oil",
                "allergens": "en:milk",
                "nutriscore_grade": "e",
                "image_url": "https://x/n.jpg",
                "nutriments": {"energy-kcal_100g": 539},
            },
        }

    monkeypatch.setattr("app.api.v1.endpoints.food.openfoodfacts.barcode", fake_barcode)
    resp = await client.get("/api/v1/food/barcode/3017620422003")
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "Nutella"
    assert body["nutriscore"] == "e"


async def test_food_barcode_missing_404(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fake_barcode(_c, _code: str) -> dict:
        return {"status": 0, "status_verbose": "product not found"}

    monkeypatch.setattr("app.api.v1.endpoints.food.openfoodfacts.barcode", fake_barcode)
    resp = await client.get("/api/v1/food/barcode/0000")
    assert resp.status_code == 404


async def test_weather_current(client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_current(_c, _lat: float, _lon: float) -> dict:
        return {
            "latitude": 47.6,
            "longitude": -122.3,
            "timezone": "America/Los_Angeles",
            "current": {
                "temperature_2m": 12.5,
                "apparent_temperature": 11.0,
                "relative_humidity_2m": 80,
                "wind_speed_10m": 4.2,
                "wind_direction_10m": 270,
                "weather_code": 3,
            },
            "daily": {"sunrise": ["2026-06-10T05:12"], "sunset": ["2026-06-10T21:09"]},
        }

    monkeypatch.setattr("app.api.v1.endpoints.weather.open_meteo.current", fake_current)
    resp = await client.get("/api/v1/weather/current?lat=47.6&lon=-122.3")
    assert resp.status_code == 200
    body = resp.json()
    assert body["temperature"] == 12.5
    assert body["sunrise"] == "2026-06-10T05:12"


async def test_weather_forecast_days(client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_forecast(_c, _lat: float, _lon: float, days: int) -> dict:
        return {
            "latitude": 47.6,
            "longitude": -122.3,
            "timezone": "UTC",
            "daily": {
                "time": [f"2026-06-{10 + i:02d}" for i in range(days)],
                "weather_code": [3] * days,
                "temperature_2m_max": [20.0] * days,
                "temperature_2m_min": [10.0] * days,
                "precipitation_sum": [0.0] * days,
                "sunrise": ["2026-06-10T05:00"] * days,
                "sunset": ["2026-06-10T21:00"] * days,
            },
        }

    monkeypatch.setattr("app.api.v1.endpoints.weather.open_meteo.forecast", fake_forecast)
    resp = await client.get("/api/v1/weather/forecast?lat=47.6&lon=-122.3&days=3")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["days"]) == 3


async def test_weather_lat_out_of_range(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/weather/current?lat=999&lon=0")
    assert resp.status_code == 422
