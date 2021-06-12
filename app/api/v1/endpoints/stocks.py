from typing import List, Optional

from fastapi import APIRouter, HTTPException
import yfinance as yf
from pydantic import BaseModel

router = APIRouter()


class StockPeriod(BaseModel):
    open: float
    close: float
    high: float
    low: float
    volume: int
    dividends: float
    splits: int

    def __init__(self, **kwargs):
        kwargs['open'] = kwargs['Open']
        kwargs['close'] = kwargs['Close']
        kwargs['high'] = kwargs['High']
        kwargs['low'] = kwargs['Low']
        kwargs['volume'] = kwargs['Volume']
        kwargs['dividends'] = kwargs['Dividends']
        kwargs['splits'] = kwargs['Stock Splits']
        super().__init__(**kwargs)


class Stock(BaseModel):
    symbol: str
    name: Optional[str]
    name_short: str
    sector: Optional[str]
    industry: Optional[str]
    logo_url: str
    history_period: str
    history: List[StockPeriod]
    price: Optional[float]
    change: float

    def __init__(self, **kwargs):
        kwargs['name'] = kwargs['longName']
        kwargs['name_short'] = kwargs['shortName']
        kwargs['price'] = kwargs['regularMarketPrice']
        super().__init__(**kwargs)


@router.get('/{ticker}', response_model=Stock)
async def get_ticker(ticker: str):
    t = yf.Ticker(ticker)
    if 'symbol' not in t.info:
        raise HTTPException(status_code=404, detail='Ticker Not Found')

    h = t.history(period='30d').to_dict('records')
    info = {key: (t.info[key] if key in t.info else None) for key in ['sector', 'industry', 'regularMarketPrice', 'symbol', 'shortName', 'longName', 'logo_url']}
    return {
        **info,
        'history': h,
        'history_period': '1d',
        'change': h[-1]['Close']-h[-2]['Close'] if len(h) > 1 else 0
    }
