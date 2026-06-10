import time
from collections.abc import Awaitable, Callable
from typing import Any

import httpx
import structlog
from fastapi import HTTPException

log = structlog.get_logger()

DEFAULT_TIMEOUT = httpx.Timeout(5.0, connect=2.0)


class UpstreamError(Exception):
    def __init__(self, *, provider: str, status: int, code: str, message: str) -> None:
        self.provider = provider
        self.status = status
        self.code = code
        self.message = message
        super().__init__(f"{provider}: {code} ({status}) {message}")


def make_client(base_url: str, *, headers: dict[str, str] | None = None) -> httpx.AsyncClient:
    return httpx.AsyncClient(base_url=base_url, timeout=DEFAULT_TIMEOUT, headers=headers or {})


async def request(
    client: httpx.AsyncClient,
    *,
    provider: str,
    method: str,
    path: str,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> httpx.Response:
    start = time.perf_counter()
    status = 0
    try:
        resp = await client.request(method, path, params=params, headers=headers)
        status = resp.status_code
        if resp.status_code >= 500:
            raise UpstreamError(
                provider=provider,
                status=resp.status_code,
                code="upstream_5xx",
                message=resp.text[:200],
            )
        if resp.status_code >= 400:
            raise UpstreamError(
                provider=provider,
                status=resp.status_code,
                code="upstream_4xx",
                message=resp.text[:200],
            )
        return resp
    except httpx.TimeoutException as err:
        raise UpstreamError(
            provider=provider, status=504, code="timeout", message=str(err)
        ) from err
    except httpx.HTTPError as err:
        raise UpstreamError(
            provider=provider, status=502, code="transport", message=str(err)
        ) from err
    finally:
        latency_ms = round((time.perf_counter() - start) * 1000, 2)
        log.info(
            "upstream",
            provider=provider,
            method=method,
            path=path,
            status=status,
            latency_ms=latency_ms,
        )


def translate_upstream(err: UpstreamError) -> HTTPException:
    return HTTPException(
        status_code=502,
        detail={"upstream": err.provider, "code": err.code, "message": err.message},
    )


async def with_upstream(coro: Callable[[], Awaitable[Any]]) -> Any:
    try:
        return await coro()
    except UpstreamError as err:
        raise translate_upstream(err) from err
