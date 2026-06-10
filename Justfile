default:
    @just --list

dev:
    uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

test *ARGS:
    uv run pytest {{ARGS}}

lint *ARGS:
    uv run ruff check {{ARGS}} .

format *ARGS:
    uv run ruff format {{ARGS}} .

typecheck:
    uv run pyright

migrate:
    uv run alembic upgrade head

codegen-friendly:
    uv run python -c "import urllib.request; print(urllib.request.urlopen('http://localhost:8000/api/v1/openapi.json').read().decode())" > openapi.json
