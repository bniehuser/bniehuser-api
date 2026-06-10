# bniehuser-api

FastAPI backend for [bniehuser.com](https://bniehuser.com). Toy / playground
backend — small user system, a handful of external-API proxies (stocks,
recipes, food, weather), and a websocket chat hub. Sibling SPA lives at
`../react/`.

For architecture and working notes see [`CLAUDE.md`](./CLAUDE.md); for the
2026 modernization plan and gating criteria see [`PROJECT.md`](./PROJECT.md).
Per-substep execution detail is in [`docs/modernization-plan.md`](./docs/modernization-plan.md).

## Local dev

Requires `uv` (https://docs.astral.sh/uv/) and `just`. Postgres connection
is composed from `PG{HOST,PORT,USER,PASSWORD,DATABASE}` env vars; named
secrets (`SECRET_KEY`, `FORWARD_HMAC_SECRET`, etc.) read from `.env` —
see `PROJECT.md` for the full list.

```bash
uv sync                    # resolve + create .venv
just dev                   # uvicorn on :8000 with --reload
just test                  # pytest
just lint                  # ruff check
just format                # ruff format
just typecheck             # pyright
just migrate               # alembic upgrade head
```

## Provenance

Originally a 2021 `full-stack-fastapi-postgresql` template; modernized
to a 2026 stack (uv / Python 3.12 / Pydantic v2 / SQLModel / Alembic /
async psycopg v3) in 2026-06. The legacy Discord bot lives at
`legacy/discord-bot/` pending extraction to a separate `hub-bot` repo.
