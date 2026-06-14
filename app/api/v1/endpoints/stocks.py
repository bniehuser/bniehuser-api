from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel, ConfigDict, model_validator

from app.clients import finnhub, twelvedata
from app.clients._base import with_upstream
from app.clients.pool import get as get_client

router = APIRouter()


class Stock(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    symbol: str
    name: str | None = None
    exchange: str | None = None
    industry: str | None = None
    logo_url: str | None = None
    currency: str | None = None
    price: float
    change: float
    change_percent: float
    high: float
    low: float
    open: float
    previous_close: float
    timestamp: int

    @model_validator(mode="before")
    @classmethod
    def _remap(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        quote = data.get("quote", {})
        profile = data.get("profile", {})
        return {
            "symbol": data.get("symbol") or profile.get("ticker", ""),
            "name": profile.get("name"),
            "exchange": profile.get("exchange"),
            "industry": profile.get("finnhubIndustry"),
            "logo_url": profile.get("logo"),
            "currency": profile.get("currency"),
            "price": quote.get("c"),
            "change": quote.get("d"),
            "change_percent": quote.get("dp"),
            "high": quote.get("h"),
            "low": quote.get("l"),
            "open": quote.get("o"),
            "previous_close": quote.get("pc"),
            "timestamp": quote.get("t"),
        }


class Candle(BaseModel):
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: int


@router.get("/{ticker}", response_model=Stock)
async def get_stock(ticker: str) -> Stock:
    client = get_client("finnhub")
    symbol = ticker.upper()

    async def fetch() -> Stock:
        quote = await finnhub.quote(client, symbol)
        profile = await finnhub.profile(client, symbol)
        return Stock.model_validate({"symbol": symbol, "quote": quote, "profile": profile})

    return await with_upstream(fetch)


@router.get("/{ticker}/history", response_model=list[Candle])
async def get_stock_history(
    ticker: str,
    interval: str = Query("1day"),
    outputsize: int = Query(30, ge=1, le=5000),
) -> list[Candle]:
    client = get_client("twelvedata")
    symbol = ticker.upper()

    async def fetch() -> list[Candle]:
        data = await twelvedata.time_series(client, symbol, interval, outputsize)
        values = data.get("values", [])
        candles = [
            Candle(
                date=v["datetime"],
                open=float(v["open"]),
                high=float(v["high"]),
                low=float(v["low"]),
                close=float(v["close"]),
                volume=int(v.get("volume") or 0),
            )
            for v in values
        ]
        # Twelve Data returns descending by date — reverse to ascending for charting.
        candles.reverse()
        return candles

    return await with_upstream(fetch)
