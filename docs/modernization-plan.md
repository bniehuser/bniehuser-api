# Modernization plan — pass-by-pass execution

This is the detailed execution guide for the six substeps in `PROJECT.md`.
Each pass lands as one commit on `modernize-2026` (branch off `main`).
Final PR back to `main` when SPA round-trips green (substep 6).

## Substep 1: Tooling baseline (no api-runtime behavior change)

### Delete
- `poetry.lock`
- `pyproject.toml` (Poetry one — recreated below)
- `supervisord.conf`
- `.idea/`
- `app/external_api/fio_rest.yaml` (unused upstream openapi spec)

### Move (park legacy bot)
- `app/bot_daemon.py` → `legacy/discord-bot/bot_daemon.py`
- `app/core/messaging.py` → `legacy/discord-bot/messaging.py`
- The `legacy/` tree is not imported by the runtime path after this
  substep; substep 3 inlines the small `SocketMessage` shape it
  needs into `app/api/v1/endpoints/websocket.py` rather than reaching
  back into `legacy/`.
- `docs/discord-bot-port.md` already captures the bot's behavioral
  contract for hub-bot — referenced by the legacy code, deleted with
  the legacy code in substep 4.

### Create
- `pyproject.toml` via `uv init` then `uv add`:
  - Runtime: `fastapi`, `uvicorn[standard]`, `sqlmodel`,
    `psycopg[binary]`, `alembic`, `pyjwt`, `bcrypt`, `httpx`,
    `structlog`, `python-multipart`, `pydantic-settings`.
  - Dev (`uv add --dev`): `pytest`, `pytest-asyncio`, `ruff`, `pyright`.
- `uv.lock` (produced by `uv lock`).
- `.python-version` containing `3.12`.
- `Justfile` with recipes: `dev`, `test`, `lint`, `format`, `typecheck`,
  `migrate`, `codegen-friendly`.
- `README.md` rewrite — actual stack, how to run locally, provenance
  note (this codebase started in 2021; modernized 2026).

> No `.hooks/` directory. Infra owns the deploy action (`git pull
> --ff-only && docker exec python supervisorctl restart api`); the
> tenant repo ships zero infra-aware files. See `PROJECT.md` Completion
> criteria.

### Acceptance

- `uv run pytest` runs (even if every test fails, just so the environment
  resolves).
- `uv run ruff check .` clean (after auto-fixes).
- `uv run pyright` reports something sensible (not crashes).
- `git diff --stat` shows only tooling files + the five deletions
  + two file moves into `legacy/discord-bot/` + the two new docs
  (`docs/discord-bot-port.md`, `docs/backlog.md` if not already
  present from the planning pass).

## Substep 2: Data layer rewrite

### Collapse

Five legacy files become three:

| Legacy | New |
|---|---|
| `app/db/session.py` | `app/db.py` (engine + Session factory) |
| `app/db/base.py` | merged into `app/db.py` |
| `app/db/base_class.py` | merged into `app/db.py` |
| `app/db/init_db.py` | folded into `app/main.py` lifespan (see Q6 in `PROJECT.md`) |
| `app/domain/user/{models,schemas,crud}.py` | `app/models/user.py` + `app/crud/user.py` |

### New shape

- `app/db.py`:
  - `engine = create_async_engine(settings.database_url, ...)` —
    `psycopg` v3 supports async over the same `postgresql+psycopg://...`
    URL composed from libpq env vars (`PG{HOST,PORT,USER,PASSWORD,DATABASE}`).
    See `PROJECT.md` Issue H (URL composition) and Issue J (async rationale).
  - `async def get_session() -> AsyncGenerator[AsyncSession, None]: ...`
    yielding `sqlmodel.ext.asyncio.session.AsyncSession` for FastAPI deps.
- `app/models/user.py`:
  - Single `class User(SQLModel, table=True): ...` — DB columns +
    pydantic validation in one class.
- `app/crud/user.py`:
  - Async helpers: `get_by_email`, `create`, `authenticate`,
    `is_superuser`.
  - Use SA 2.x async style: `await session.exec(select(User).where(...))`.
  - Watch for SA-1-isms in the legacy `domain/user/crud.py` that don't
    translate (`db.query(...)`, sync `db.commit()` without await).

### Migrations

- `uv run alembic init --template async migrations` (matches the
  async session strategy from `PROJECT.md` Issue J).
- Point `alembic.ini` + `migrations/env.py` at SQLModel metadata.
- Generate baseline migration: `uv run alembic revision --autogenerate -m "baseline"`.
- Commit `migrations/versions/<hash>_baseline.py`.

### Acceptance

- `uv run alembic upgrade head` against a local postgres creates the
  `user` table.
- `uv run pytest` for any test that touches the user model passes.

## Substep 3: FastAPI / Pydantic v2 cascade

Biggest pass. Touches every router.

### `app/main.py`

- Replace `app.on_event("startup"|"shutdown")` with `@asynccontextmanager`
  `lifespan` function passed to `FastAPI(lifespan=lifespan,
  openapi_version="3.0.2", openapi_url="/api/v1/openapi.json")`
  (Issue B locked to 3.0.2).
- `app.include_router(api_router, prefix="/api/v1")` — every route
  lives under `/api/v1/*` (Issue I).
- Lifespan startup calls `create_superuser_if_missing()` from
  `app/auth/bootstrap.py` (replaces the legacy `app/db/init_db.py`
  one-shot CLI — see Q6 in `PROJECT.md`). Idempotent; reads
  `BOOTSTRAP_USER_EMAIL` / `BOOTSTRAP_USER_PASSWORD` from env.
- CORS middleware: see `config.py` section below for the fix to the
  legacy char-by-char iteration bug.

### `app/core/config.py`

- Replace `pydantic.BaseSettings` with `pydantic_settings.BaseSettings`.
- `BACKEND_CORS_ORIGINS: list[AnyHttpUrl] | None = None`, parsed from
  comma-separated env via `field_validator(mode='before')`. Local-dev
  default covers Vite ports 5173-5180 (default + headroom for
  multiple SPA dev servers running concurrently). In `app/main.py`,
  wire the CORS middleware with `allow_origin_regex=r"^http://localhost:51(7[3-9]|80)$"`
  in addition to the explicit `allow_origins` list — the regex
  handles the dev-port range cleanly without enumerating eight URLs.
- Libpq env vars + composed `database_url` property per `PROJECT.md`
  Issue H. **No `DATABASE_URL` field.**
- Named secret env vars (`RAPIDAPI_KEY`, `SECRET_KEY`,
  `FORWARD_HMAC_SECRET`, `BOT_API_TOKEN`, `BOOTSTRAP_USER_EMAIL`,
  `BOOTSTRAP_USER_PASSWORD`) declared as `Settings` fields too — one
  source of truth for what the app reads from env.
- `EMAIL_RESET_TOKEN_EXPIRE_HOURS: int = 48` — referenced by legacy
  `app/utils.py` but never declared (latent AttributeError if invoked).
  Add it while migrating to `app/auth/tokens.py`.
- All other settings translate 1:1; check `model_config = SettingsConfigDict(...)`
  for env file handling.

**CORS bug fix:** legacy `BACKEND_CORS_ORIGINS` is typed `Optional[str]`
and `app/main.py` does `[str(origin) for origin in settings.BACKEND_CORS_ORIGINS]`
which iterates the string character by character. CORS has been
silently shipping nothing useful since day one. The `list[AnyHttpUrl]`
rewrite fixes this; smoke-test against a Vite dev SPA at the default
port before declaring substep 3 done.

### `app/api/v1/endpoints/health.py`

- Trivial: returns `{"status": "ok", "version": "<from pyproject>"}`.
- No DB dep. No auth. Returns 200 always.
- **Optional**, not a cutover gate (infra dropped `/health` from the
  contract — healthcheck deferred fleet-wide). Still useful as a
  no-auth liveness probe for SPA/uptime checks.

### `app/api/v1/endpoints/stocks.py`

- Biggest pydantic v2 surgery. Current code defines `Stock(BaseModel)` with
  `__init__(self, **kw)` that remaps Yahoo's PascalCase keys to snake_case.
  v2 breaks this — `__init__` doesn't run during validation.
- Replace with `@model_validator(mode='before') @classmethod def _remap(cls, data): ...`
  that does the same key transform before validation.
- yfinance call: wrap in `httpx.AsyncClient` if it's currently sync. If
  yfinance is sync-only, run via `asyncio.to_thread`.

### `app/api/v1/endpoints/recipes.py`

- Drop the `spoonacular` SDK dep entirely.
- Replace with `app/clients/spoonacular.py` — thin `httpx.AsyncClient`
  wrapper against `https://spoonacular-recipe-food-nutrition-v1.p.rapidapi.com/`.
- API key from `settings.RAPIDAPI_KEY` (SSM-sourced).
- Same v2 model treatment as stocks if the upstream JSON needs key remapping.

### `app/api/v1/endpoints/auth.py`

- Replace `python-jose` with `pyjwt`:
  - `jwt.encode(payload, key, algorithm="HS256")`,
  - `jwt.decode(token, key, algorithms=["HS256"])`.
- Replace `passlib.context.CryptContext` with direct `bcrypt`:
  - `bcrypt.hashpw(password.encode(), bcrypt.gensalt())`,
  - `bcrypt.checkpw(password.encode(), hashed)`.
- Token claims unchanged (`sub`, `exp`, etc).
- `OAuth2PasswordBearer(tokenUrl="/api/v1/login/access-token")` —
  matches the `/api/v1` prefix from Issue I.
- Password reset (Issue L):
  - Move `generate_password_reset_token` / `verify_password_reset_token`
    from `app/utils.py` to a new `app/auth/tokens.py`, rewritten on
    `pyjwt`. Delete `app/utils.py`.
  - `POST /password-recovery/{email}` — look up user, generate token
    server-side (exercise the path), return **501 Not Implemented**
    with body `{"msg": "Password reset email delivery is not yet
    configured."}`. Never return the token in the response body.
    Email-sender wiring is filed in `docs/backlog.md`.
  - `POST /reset-password/` — fully functional: takes token + new
    password, verifies via `app/auth/tokens.py`, updates the user.

### `app/api/v1/endpoints/users.py`

- Adapt to the async `AsyncSession` from substep 2 (Issue J). Every
  endpoint in this module becomes `async def`; every CRUD call is
  `await`-ed.
- Keep endpoint shapes (request/response models, paths, status codes) —
  SPA openapi codegen is tied to them. Any contract change cascades to
  SPA work in substep 6. The path prefix changes (Issue I) but
  that's a free byproduct of `include_router(prefix=...)`, not a
  per-endpoint edit.

### `app/api/v1/endpoints/websocket.py`

Behavioral change biggest here:

- `/ws/{client_id}` for SPA clients — URL relative (final mount:
  `/api/v1/ws/{client_id}`). Issue D fix: switch
  `ConnectionManager.connections` to an instance attribute, not the
  class-level dict.
- **Origin-check on WS upgrade (Issue E, layer 1):** reject handshake
  unless `Origin` is `https://bniehuser.com` or matches the local-dev
  regex used for CORS. Done inside the WS handler — FastAPI doesn't
  apply CORS middleware to WS upgrades.
- Inline the `SocketMessage` / `SocketScope` / `SocketSource` shapes
  needed for routing into this module (or `app/api/v1/endpoints/_socket_message.py`).
  Don't import from `legacy/discord-bot/messaging.py` — the legacy
  tree is parked, not a runtime dep.
- **New `/internal/discord/incoming` HTTP endpoint** — full HMAC
  contract in `PROJECT.md` Issue K. Body: `{scope, sender, message}`.
  On accept, fans out to connected SPA clients per the PUBLIC/PRIVATE
  rules captured in `docs/discord-bot-port.md`.
- **New `discord_outbound(scope, message)` helper** in the same module:
  - Posts to `http://hub-bot:9000/send` with `Authorization: Bearer
    $BOT_API_TOKEN`.
  - `httpx.AsyncClient(timeout=3.0)` per request; log+drop on failure
    (don't crash the WS handler on bot unreachable).
- Until hub-bot is applied (gate on substep 4), `discord_outbound`
  silently no-ops on connection refused. That's intentional — keeps
  the modernization landable without hub-bot being live.

### Acceptance

- `uv run pytest` green for all tests that don't require an external
  bot.
- `uv run uvicorn app.main:app` starts cleanly locally.
- `curl http://localhost:8000/api/v1/health` → 200.
- `curl http://localhost:8000/api/v1/openapi.json` returns the schema
  and every route in it lives under `/api/v1/*`.
- Manual: POST a HMAC-signed payload to
  `/api/v1/internal/discord/incoming` (signature per Issue K),
  observe fan-out to a connected WS client.
- Manual: open a WS connection without an allowed `Origin` header,
  observe handshake rejection (Issue E layer 1).

## Substep 4: Bot code cleanup

**Gate:** hub-bot has been applied on the hub (infra's substep §3.3
operator apply). Without that, `http://hub-bot:9000` doesn't resolve and
the websocket bot bridge silently no-ops — acceptable for develop, not
for cutover smoke.

### Delete
- `legacy/discord-bot/` (parked in substep 1 — both `bot_daemon.py`
  and `messaging.py` go).
- `docs/discord-bot-port.md` (port notes are consumed by hub-bot at
  this point — preserve a copy in the hub-bot repo if useful).
- Any vestigial imports of `discord.py`, `websocket-client`, or
  `websockets` (none should exist in `app/` since substep 1, but
  grep to confirm).

### Verify
- `grep -r "bot_daemon\|websocket-client\|discord\.py" app/ tests/`
  returns nothing.
- `uv run pytest` still green.
- End-to-end smoke: hub-bot posts an HMAC-signed payload to
  `/api/v1/internal/discord/incoming`, a connected SPA WS client
  receives the fan-out, and `discord_outbound(...)` from a chat
  message reaches hub-bot and shows up in Discord.
- No new deps need adding (the bot bridge is just `httpx` POSTs).

## Substep 5: Dev runtime

### `docker-compose.yml` (dev only)

Production runs in infra's **shared `python` container** (single
container, supervisord-managed uvicorn programs, bind-mounted `/srv/api`
+ `uv sync --frozen` at program start). The catalog's `serve:` command
runs as the program; no prod Dockerfile needed here.

Compose services:
- `api` — bind-mount the repo into a `ghcr.io/astral-sh/uv:python3.12-bookworm-slim`
  container and run `uv sync && uv run uvicorn app.main:app --host 0.0.0.0 --port 8000`
  (mirrors hub-python's runtime as closely as possible — same base
  image, same uv-sync-at-start flow, minus supervisord). Dev `.env`
  carries `PG{HOST,PORT,USER,PASSWORD,DATABASE}` + the named secrets.
- `postgres` — `postgres:16-alpine`, exposed on host `5432`, gitignored
  named volume for data.
- `bot` — pulls the hub-bot image (or builds from sibling
  `infra/stacks/hub-bot/build/`) so the websocket bridge has a real
  target. (May simplify after infra substep 3 bot extraction — see
  `infra/PROJECT.md`.)

Gitignored `.env` for local SECRETS. `.env.example` checked in with
placeholder values for all of `PG*` + named secrets above.

### Acceptance

- `docker compose up` boots all three services.
- `curl http://localhost:8000/api/v1/health` returns 200.
- Hitting an SPA-style auth endpoint (`/api/v1/login/access-token`)
  from the host works.

## Substep 6: SPA round-trip verification

- `cd ~/code/barry/bniehuser/react/ && pnpm codegen` against
  `http://localhost:8000/api/v1/openapi.json` (or against
  `https://api.bniehuser.com/api/v1/openapi.json` post-cutover).
- Confirm:
  - `RecipesService.*` methods type-check and run.
  - `StocksService.*` methods type-check and run.
  - Websocket bridge connects, receives a discord-forwarded message.
- File any SPA-side breakage as issues in the SPA repo — the api side is
  contract-stable if endpoint shapes held.

### Cross-cutting verifications

- **Q8** — apex SPA may need redeploy if it was built before
  `VITE_API_URL` was set. Check
  `cd ~/code/barry/infra && tofu state show 'data.cloudflare_pages_project.web'`
  or the CF dashboard for last deploy timestamp.
- **Routing prefix (Issue I)** — every route now lives under
  `/api/v1/*`. SPA's `VITE_API_URL` (`https://api.bniehuser.com`)
  remains the base; codegen picks up the new prefix automatically
  from the openapi spec. Worth confirming the SPA's old hand-written
  call sites (if any) also flow through the generated services.
- **OpenAPI 3.0.2 pin (Issue B)** — if the SPA's current codegen tool
  is `openapi-typescript-codegen`, no change needed. The backlog
  follow-up (`docs/backlog.md`) is to swap to a 3.1-aware tool
  (`@hey-api/openapi-ts`, `openapi-typescript` + `openapi-fetch`, or
  `orval`) and drop the pin. Not a cutover gate.

### Acceptance

- SPA load → login → fetch recipes → ws-receive a discord message all
  work end-to-end against `https://api.bniehuser.com`.
- PR `modernize-2026` → `main`. Merge.
- Signal infra session: api modernization complete. Infra updates
  `PROJECT.md` status table accordingly.
