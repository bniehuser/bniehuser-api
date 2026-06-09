# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

`bniehuser-api` is the FastAPI backend for the personal site at `bniehuser.com` (SPA lives in sibling repo `../react`). It is intentionally a toy / playground backend — a small user system, a couple of external-API proxies (stocks via `yfinance`, recipes via RapidAPI Spoonacular), and a websocket chat hub. Expect to add and discard features freely. There are no real production users beyond the maintainer.

## Repository state: mid-modernization

The code on disk is a 2021-era codebase (Python 3.8, FastAPI 0.65, Pydantic v1, SQLAlchemy 1.x, Poetry, `python-jose`, `passlib`, in-repo `discord.py` bot). Modernization to a 2026 stack is planned in six sequential substeps on a `modernize-2026` branch.

**Before doing anything substantive, read these — they are authoritative over this file when they disagree:**

- `PROJECT.md` — overarching plan, completion-criteria gates for the infra `hub-python` cutover, cross-cutting decisions (Issues B/D/E/H/I/J/K/L, Q6, Q8), status table.
- `docs/modernization-plan.md` — per-substep execution detail (what to delete, what to create, acceptance criteria).
- `docs/discord-bot-port.md` — behavioral contract for the legacy Discord bot, captured for the eventual hub-bot extraction. Created in substep 1, deleted in substep 4.
- `docs/backlog.md` — items deferred beyond the modernization cutover (email sender, OpenAPI 3.1 codegen, ws-auth layer 2, caching, observability, etc).

Target stack (decided, do not relitigate without cause): `uv` + Python 3.12, `ruff` + `pyright`, FastAPI 0.115+ with Pydantic v2 + `pydantic-settings`, `SQLModel` + Alembic + `psycopg` v3, `pyjwt` + direct `bcrypt` (drop `passlib` and `python-jose`), `httpx`, `structlog`, `docker compose` + `Justfile` for local dev.

## High-level architecture (current code on disk)

- `app/main.py` builds `FastAPI(...)`, applies CORS, mounts `api_router` at root. OpenAPI is served at `/api/v1/openapi.json` — this URL is load-bearing because the SPA runs `openapi-typescript-codegen` against it.
- `app/api/v1/api.py` is the only router aggregator. Sub-routers in `app/api/v1/endpoints/`:
  - `auth.py` — `/login/access-token` (OAuth2 password form), test-token, password-reset stubs.
  - `users.py` — `/users/*` CRUD, plus `/users/open` self-registration (gated on `USERS_OPEN_REGISTRATION`).
  - `stocks.py` — `/stocks/{ticker}` proxies `yfinance`. Pydantic models override `__init__` to remap PascalCase keys → snake_case. **This pattern breaks under Pydantic v2** (validators don't run through `__init__`); rewrite as `@model_validator(mode='before')` during substep 3 — same applies to `recipes.py`.
  - `recipes.py` — `/recipes/*` proxies the RapidAPI Spoonacular endpoint via the legacy `spoonacular` SDK. Substep 3 replaces with a thin `httpx` client.
  - `websocket.py` — `/ws/{client_id}` chat fan-out. `ConnectionManager.connections` is declared as a **class-level** dict (shared mutable default — Issue D); rewrite as instance attr. Uses `SocketMessage` from `app/core/messaging.py` with `SocketScope` (PUBLIC/PRIVATE/SYSTEM) and `SocketSource` (SERVER/CLIENT/BOT) routing rules.
  - `health.py` — `/health` returns 200. **Not** a cutover gate (infra deferred health checks fleet-wide), but keep it as a no-auth liveness probe.
- `app/api/deps.py` — FastAPI dependencies: `get_db` (SessionLocal), `get_current_user` / `_active_user` / `_active_superuser` (JWT decode → user lookup).
- `app/core/config.py` — `pydantic.BaseSettings` (v1). Reads `.env`. Substep 3 swaps to `pydantic_settings.BaseSettings` and replaces `database_url` with composed-from-`PG*` (see "DB connection contract" below).
- `app/core/security.py` — JWT via `python-jose`, bcrypt via `passlib`. Both get replaced in substep 3.
- `app/core/messaging.py` — `SocketMessage` Pydantic model + enum JSON codec. Substep 1 parks this to `legacy/discord-bot/messaging.py` along with `bot_daemon.py`. Substep 3 inlines the small `SocketMessage` shape it still needs into `app/api/v1/endpoints/websocket.py` (the new HMAC payload type).
- `app/db/{base,base_class,session,init_db}.py` + `app/domain/{crud,user/{models,schemas,crud}}.py` — classic SQLAlchemy-1 layered layout cloned from the full-stack-fastapi-postgresql template. `CRUDBase` generic is in `app/domain/crud.py`; `CRUDUser` extends it. Substep 2 collapses all of this to `app/db.py` + `app/models/user.py` + `app/crud/user.py` using `SQLModel`. `db.query()` calls must become `session.exec(select(...))` (SA 2.x).
- `app/initial_data.py` — one-shot CLI that calls `init_db()` to bootstrap the first superuser. Substep 3 folds this into the FastAPI `lifespan` startup hook as an idempotent `create_superuser_if_missing()` (Q6 in `PROJECT.md`).
- `app/bot_daemon.py` — standalone `discord.py` 1.7.2 process that opens a websocket back to `/ws/bot` and bridges Discord ↔ chat. **Substep 1 parks this to `legacy/discord-bot/bot_daemon.py`** (drops it from the runtime path, preserves the code) with behavioral contract captured in `docs/discord-bot-port.md` for the eventual hub-bot extraction. Substep 4 deletes the legacy tree once hub-bot is live. The new bridge is `/api/v1/internal/discord/incoming` (HMAC-verified inbound) plus a `discord_outbound(...)` helper that POSTs to `http://hub-bot:9000/send`.
- `app/external_api/fio_rest.yaml` — an unused OpenAPI spec checked in; not referenced by code.

## DB connection contract

The deployed runtime (infra's `hub-python` shared container) injects libpq env vars (`PGHOST`, `PGPORT`, `PGUSER`, `PGPASSWORD`, `PGDATABASE`) into the supervisord program env. **It does not inject `DATABASE_URL`.** During substep 2/3, the new `Settings` class declares those five fields and exposes a `database_url` property that composes `postgresql+psycopg://...`. Local dev `.env` must use the same `PG*` shape so the code path is identical. See `PROJECT.md` Issue H.

The current code on disk still reads `DATABASE_URL` directly — that field goes away in substep 3.

## SPA contract — keep openapi shapes stable

`../react` runs `pnpm codegen` against `/api/v1/openapi.json` and consumes `RecipesService.*`, `StocksService.*`, the auth flow, and the websocket bridge. Endpoint paths and response shapes are part of the cross-repo contract. Any change ripples to the SPA in substep 6. When refactoring a router, preserve the externally visible shape unless a deliberate break is being scheduled.

FastAPI 0.115+ emits OpenAPI 3.1 by default; the SPA's codegen historically struggles with 3.1's nullable shape (Issue B). The fallback is `FastAPI(openapi_version="3.0.2")`. Decide at substep 3 time.

## Tests

`tests/conftest.py` exists but is empty; there is no real test suite yet. Acceptance criteria across substeps target `uv run pytest` resolving and individual touched modules being tested — do not assume an existing suite to lean on.

## Commands

The repo is currently in its **pre-modernization** Poetry state. Commands below reflect that. Substep 1 replaces them with `uv` + a `Justfile` (`just dev`, `just test`, `just lint`, `just format`, `just typecheck`, `just migrate`, `just codegen-friendly`); switch to those once substep 1 lands.

```bash
poetry install
poetry run uvicorn app.main:app --reload     # dev server
poetry run python -m app.initial_data         # one-shot superuser bootstrap (legacy)
poetry run pytest                             # currently no-op (empty conftest)
```

Post-substep-1, expect:

```bash
uv sync
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
uv run pytest
uv run ruff check . && uv run ruff format .
uv run pyright
uv run alembic upgrade head
```

## Working-style notes for this repo

- Modernization commits land on the `modernize-2026` branch, one commit per substep, PR to `main` at the end.
- Substep 4 (delete `bot_daemon.py` and `core/messaging.py`) is **blocked** until the infra `hub-bot` substack is applied — don't pull the rug while substep 3's websocket bridge still has nothing to talk to in dev.
- Live-looking secrets exist in the local `.env` (gitignored). Do not echo `.env` contents in output, command examples, or commit messages. Read from the file at runtime if a command needs them.
- This session and the infra session at `~/code/barry/infra/` coordinate via signals in `PROJECT.md` ("api ready" once gate items are green). Don't read into `../react/` or `~/code/barry/infra/` from inside this repo's session unless explicitly asked — those have their own plans and are easy to get sidetracked into.
