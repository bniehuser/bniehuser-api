from fastapi import APIRouter
import yfinance as yf

router = APIRouter()


@router.get('/{ticker}')
async def get_ticker(ticker: str):
    t = yf.Ticker(ticker)
    return {
        'info': {key: t.info[key] for key in ['sector', 'industry', 'regularMarketPrice', 'symbol', 'shortName', 'longName', 'logo_url']},
        'history': t.history(period='7d').to_dict('records')
    }
