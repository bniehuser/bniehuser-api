from typing import List

from fastapi import APIRouter
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
    name: str
    name_short: str
    sector: str
    industry: str
    logo_url: str
    history_period: str
    history: List[StockPeriod]
    price: float
    change: float

    def __init__(self, **kwargs):
        kwargs['name'] = kwargs['longName']
        kwargs['name_short'] = kwargs['shortName']
        kwargs['price'] = kwargs['regularMarketPrice']
        super().__init__(**kwargs)


@router.get('/{ticker}')
async def get_ticker(ticker: str):
    t = yf.Ticker(ticker)
    h = t.history(period='7d').to_dict('records')
    info = {key: t.info[key] for key in ['sector', 'industry', 'regularMarketPrice', 'symbol', 'shortName', 'longName', 'logo_url']}
    return {
        **info,
        'history': h,
        'history_period': '1d',
        'change': h[-1]['Close']-h[-2]['Close']
    }
