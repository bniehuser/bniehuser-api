from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from app.api.v1.api import api_router
from app.auth.bootstrap import create_superuser_if_missing
from app.core.config import settings
from app.core.logging import configure_structlog
from app.core.middleware import RequestLoggingMiddleware

log = structlog.get_logger()


@asynccontextmanager
async def lifespan(_: FastAPI):
    configure_structlog()
    await create_superuser_if_missing()
    log.info("startup_complete")
    yield
    log.info("shutdown_complete")


app = FastAPI(
    title=settings.app_name,
    lifespan=lifespan,
    openapi_url="/api/v1/openapi.json",
)
# FastAPI 0.115+ hardcodes 3.1.0; the constructor arg is no longer honored.
# Issue B locks to 3.0.2 for SPA codegen compatibility.
app.openapi_version = "3.0.2"

app.add_middleware(
    CORSMiddleware,
    allow_origins=[str(origin).rstrip("/") for origin in settings.BACKEND_CORS_ORIGINS],
    allow_origin_regex=settings.BACKEND_CORS_ORIGIN_REGEX,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestLoggingMiddleware)

app.include_router(api_router, prefix="/api/v1")
