default:
    @just --list

dev:
    uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

test:
    uv run pytest

lint:
    uv run ruff check .

format:
    uv run ruff format .

typecheck:
    uv run pyright

migrate:
    uv run alembic upgrade head

codegen-friendly:
    uv run python -c "import urllib.request; print(urllib.request.urlopen('http://localhost:8000/api/v1/openapi.json').read().decode())" > openapi.json
