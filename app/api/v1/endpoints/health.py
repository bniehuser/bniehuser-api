from importlib.metadata import PackageNotFoundError, version

from fastapi import APIRouter

router = APIRouter()

try:
    _version = version("bniehuser-api")
except PackageNotFoundError:
    _version = "0.0.0"


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "version": _version}
