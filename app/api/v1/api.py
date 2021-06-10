from fastapi import APIRouter

from .endpoints import health, auth, users, stocks


api_router = APIRouter()

api_router.include_router(auth.router, tags=["Authentication"])
api_router.include_router(users.router, prefix="/users", tags=["Users"])
api_router.include_router(stocks.router, prefix="/stocks", tags=["Stocks"])
api_router.include_router(health.router, tags=["Utilities"])


@api_router.get('/')
async def root():
    return {"status": "online"}
