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
  - Dev (`uv add --dev`): `pytest`, `pytest-asyncio`,
    `testcontainers[postgres]`, `ruff`, `pyright`. (`httpx` is already
    a runtime dep — used as `AsyncClient` in tests too, no separate
    add.)
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
  - Columns: `id`, `username`, `email` (unique), `hashed_password`,
    `is_active`, `is_superuser`, plus three tracking dates folded in
    at the baseline (decided 2026-06-09 — cheaper now than as a
    follow-up migration):
    - `created_at: datetime` —
      `sa_column_kwargs={"server_default": text("now()")}`, immutable.
    - `updated_at: datetime` — `server_default=text("now()")` +
      `onupdate=func.now()` so any `UPDATE` bumps it without
      app-side code.
    - `last_login: datetime | None = None` — nullable; set
      imperatively by `crud/user.py`'s `authenticate()` on success
      (see below).
- `app/crud/user.py`:
  - Async helpers: `get_by_email`, `create`, `authenticate`,
    `is_superuser`.
  - `authenticate()`: on a successful password check, set
    `user.last_login = datetime.now(UTC)` and `await session.commit()`
    before returning. Single source of truth for the bump; the
    endpoint stays dumb.
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
  `user` table with all eight columns including the three tracking
  dates.
- `tests/conftest.py` wires a session-scoped `testcontainers[postgres]`
  fixture + an async DB session fixture per test (decided 2026-06-09 —
  smoke-test-only scope, not coverage). `tests/test_user_model.py`
  smoke-tests `crud/user.create`, `crud/user.authenticate` (asserts
  `last_login` is bumped on success, untouched on failure), and the
  `updated_at` auto-bump (read → mutate → re-read).
- `uv run pytest` green.

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
- Lifespan startup also calls
  `app.core.logging.configure_structlog()` and the
  `RequestLoggingMiddleware` is registered ahead of CORS. See
  `### Observability` below for shape.
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
- Named secret env vars declared as `Settings` fields — one source of
  truth for what the app reads from env. Final cutover set
  (post-2026-06-09 external-API decisions):
  - `SECRET_KEY` — JWT signing.
  - `FORWARD_HMAC_SECRET` — `/internal/discord/incoming` HMAC.
  - `BOT_API_TOKEN` — outbound auth to `http://hub-bot:9000/send`.
  - `BOOTSTRAP_USER_EMAIL`, `BOOTSTRAP_USER_PASSWORD` — lifespan
    superuser bootstrap (Q6).
  - `FINNHUB_API_KEY` — stocks proxy (replaces yfinance).
  - `SPOONACULAR_API_KEY` — recipes proxy (replaces RapidAPI).
  - **Drops** `RAPIDAPI_KEY` on this commit.
  - Keyless upstreams (`TheMealDB`, `OpenFoodFacts`, `Open-Meteo`)
    declare no settings field.
  - Cross-repo signal: infra catalog `needs.secrets[]` for the api
    program in the python-app tenant has to update to match
    (`+FINNHUB_API_KEY`, `+SPOONACULAR_API_KEY`, `-RAPIDAPI_KEY`).
    Captured in `PROJECT.md` completion criteria.
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

### `app/api/v1/api.py`

Router aggregator — register the two new sub-routers added in this
substep alongside the existing ones (auth, users, stocks, recipes,
websocket, health):

```python
api_router.include_router(food.router,    prefix="/food",    tags=["food"])
api_router.include_router(weather.router, prefix="/weather", tags=["weather"])
```

### `app/clients/_base.py` (new — uniform external-API surface)

Substep 3 introduces an `app/clients/` package. Every external upstream
(`finnhub`, `spoonacular`, `openfoodfacts`, `themealdb`, `open_meteo`)
lives here as a thin `httpx.AsyncClient` wrapper. `_base.py` holds the
shared conventions called out in `docs/backlog.md` (uniform external-API
surface) so each per-provider client is small and consistent:

- Default `httpx.AsyncClient(timeout=httpx.Timeout(5.0, connect=2.0))`
  with a single shared instance per provider, created at lifespan startup
  and closed at shutdown.
- A normalized error envelope. Upstream timeout / 5xx / non-2xx → raise
  a small `UpstreamError` (provider, status, code, message). Endpoints
  catch and translate to HTTP 502 with body
  `{"detail": {"upstream": "<provider>", "code": "...", "message": "..."}}`.
- Structured-log hook (`structlog`) — every upstream call emits
  `{provider, method, path, status, latency_ms}` whether it succeeded
  or failed.
- Retry policy: **none** at this layer. Retries belong in a caching
  layer (filed in `docs/backlog.md`). Keep clients dumb and fast.

Endpoints below all delegate to these clients — no router calls `httpx`
directly. This is the lock-in for the "uniform request/response/error
shape regardless of upstream" principle.

### Observability — `app/core/logging.py` + request middleware

`structlog` is in the runtime dep set from substep 1; substep 3 wires
it. Decided 2026-06-09 (originally backlog'd) — the cost-of-no-logs
when the first prod thing breaks outweighs the ~30 lines of wiring.

- `app/core/logging.py`:
  - `configure_structlog()` — JSON renderer when `sys.stderr.isatty()`
    is false, console renderer when it is. Bind `service=bniehuser-api`
    and `version=<pyproject>` at process boot.
  - Standard processors: `add_log_level`, `TimeStamper(fmt="iso")`,
    `format_exc_info`, `merge_contextvars`, then the renderer.
- `app/core/middleware.py` — `RequestLoggingMiddleware` as raw ASGI
  middleware (not `BaseHTTPMiddleware`, which buffers streaming
  responses). Per request:
  - generate `request_id = uuid4().hex[:12]`,
  - bind it via `structlog.contextvars.bind_contextvars(request_id=...)`
    so every log line inside the request inherits it,
  - on completion emit
    `{event="request", request_id, method, path, status, latency_ms}`.
  - Wire it in `app/main.py` *before* CORS so preflight OPTIONS
    requests also get logged.
- The upstream-call log line from `app/clients/_base.py` automatically
  inherits `request_id` via the contextvar binding, so an upstream
  failure is greppable back to the originating request.

No log-destination wiring here — stdout/stderr is the contract with
`hub-python`'s supervisord, which captures both.

### `app/api/v1/endpoints/stocks.py`

**Decided 2026-06-09:** swap yfinance for Finnhub as the primary
upstream. Rationale in `docs/backlog.md` (research output landed at
`~/research/2026-06-09-free-public-apis/`). yfinance was the original
fragility flag motivating the modernization; Finnhub is real REST
(not Yahoo scraping), free-tier 60 req/min, US equities + crypto + FX
+ fundamentals + WebSocket from one key.

- New `app/clients/finnhub.py` — thin `httpx.AsyncClient` wrapper around
  `https://finnhub.io/api/v1/`. Auth is `?token=<FINNHUB_API_KEY>` query
  param. Methods needed for the current SPA contract: `quote(symbol)`,
  `profile(symbol)`, `candles(symbol, resolution, from_, to)`. Mirror
  the existing `/stocks/{ticker}` response shape so the SPA codegen
  doesn't churn — Finnhub's JSON gets normalized in the client, the
  endpoint returns the same `Stock` model.
- `Stock(BaseModel)` keeps the v2 surgery (the upstream now has its own
  key naming; the `@model_validator(mode='before')` handles the
  Finnhub → bniehuser remap instead of the Yahoo PascalCase remap).
- Drop `yfinance` from `pyproject.toml`. Drop `import yfinance` from
  the endpoint.
- API key from `settings.FINNHUB_API_KEY` (SSM-sourced — needs adding
  to infra catalog `needs.secrets[]`; see `PROJECT.md` completion
  criteria).
- **Backlog seed** (file in `docs/backlog.md` if not already there):
  Finnhub also exposes a WebSocket trades stream and a news endpoint.
  Both are real extensions to the proxy surface, not part of this
  cutover.

### `app/api/v1/endpoints/recipes.py`

Primary upstream stays Spoonacular, but moves off RapidAPI to direct
`api.spoonacular.com`. Substep 3 also lands two layered free
complements identified in the 2026-06-09 research:

- **Spoonacular** (primary, key-gated):
  - Drop the `spoonacular` SDK dep entirely.
  - New `app/clients/spoonacular.py` — `httpx.AsyncClient` against
    `https://api.spoonacular.com/`. Auth is `?apiKey=<key>` per
    Spoonacular's REST contract.
  - API key from `settings.SPOONACULAR_API_KEY` (SSM-sourced). Retire
    `RAPIDAPI_KEY` on the same commit.
  - Free tier is ~150 points/day direct vs ~50/day on RapidAPI free,
    and removes the RapidAPI middleman quota/auth header.
- **TheMealDB** (keyless complement — ethnic cuisine breadth):
  - New `app/clients/themealdb.py` — `httpx.AsyncClient` against
    `https://www.themealdb.com/api/json/v1/1/`. Keyless on the public
    `v1/1` path.
  - Used inside `/recipes/search`: Spoonacular primary, TheMealDB
    augments results with ethnic-cuisine matches (Asian, Latin,
    Middle Eastern) where Spoonacular's Western bias falls thin. The
    bniehuser-side response shape stays Spoonacular's — TheMealDB
    results are normalized into the same model.
  - Also useful as a quota-exhaustion fallback (if Spoonacular returns
    402 / daily quota hit, serve TheMealDB-only results with a
    `partial: true` flag in the envelope).
- **TheMealDB** is the only complement used *inside* `/recipes/*`.
  OpenFoodFacts answers a different question (product lookup, not
  recipe search), so it lives in its own router — see
  `app/api/v1/endpoints/food.py` below.

Same model-validator pattern (`@model_validator(mode='before')`) as
`stocks.py` for any upstream that needs key remapping.

### `app/api/v1/endpoints/food.py` (NEW)

Sibling to `/recipes/*` — answers "what is this product?" rather than
"find me a recipe." OpenFoodFacts is the only free barcode lookup
identified in the 2026-06-09 research, so this is a unique surface
with no overlap to Spoonacular.

- New `app/clients/openfoodfacts.py` — `httpx.AsyncClient` against
  `https://world.openfoodfacts.org/api/v2/`. Keyless, but the project
  asks consumers to send a descriptive `User-Agent`
  (`bniehuser-api/<version> (https://bniehuser.com)`). Wire that in
  the client default headers.
- New endpoint **`GET /api/v1/food/barcode/{barcode}`** — returns
  product name, brand, ingredients, allergens, nutriments, Nutri-Score,
  image URL. 404 if the barcode is unknown to OpenFoodFacts.
- Same v2 model treatment if the upstream JSON needs key remapping.

### `app/api/v1/endpoints/weather.py` (NEW)

**Decided 2026-06-09:** Open-Meteo lands as the highest-impact new
proxy surface in the modernization cutover. Selected from the research
shortlist for: zero auth (no SSM plumbing), one provider covering many
sub-surfaces (current + forecast + AQI + marine + ERA5 historical),
universal appeal (both SPA and bot consumers benefit), 10k req/day
free pool, low integration effort, composes forward with a future
geocoding addition.

- New `app/clients/open_meteo.py` — `httpx.AsyncClient` against
  `https://api.open-meteo.com/v1/` (and `air-quality-api.open-meteo.com`,
  `marine-api.open-meteo.com`, `archive-api.open-meteo.com` for the
  sibling surfaces). Keyless.
- New endpoints (cutover scope — current + forecast only; AQI / marine
  / historical filed as `docs/backlog.md` extensions):
  - **`GET /api/v1/weather/current?lat=&lon=`** — temperature, apparent
    temperature, humidity, wind, weather code, sunrise/sunset.
  - **`GET /api/v1/weather/forecast?lat=&lon=&days=`** — daily forecast
    (default 7 days, max 16 per Open-Meteo limits).
- Inputs: `lat: float`, `lon: float`, validated `-90..90` / `-180..180`
  via pydantic v2 `Field(ge=..., le=...)`. No city-name lookup in the
  cutover — that requires a geocoding upstream, deferred to backlog.
- Output models normalize Open-Meteo's structured JSON
  (`current_weather`, `daily[...]`) into a flat bniehuser shape. Same
  `@model_validator(mode='before')` pattern as stocks/recipes.
- **Backlog seed**: extend with `/weather/air-quality`,
  `/weather/marine`, `/weather/historical`, and a `/location/geocode`
  upstream (LocationIQ or Nominatim — see research report) so the
  weather endpoints accept city names instead of raw lat/lon.

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

- `tests/` has a smoke test per router using `httpx.AsyncClient`
  against the FastAPI app: `test_health`, `test_auth_login`,
  `test_users_me`, `test_stocks_quote` (Finnhub client mocked),
  `test_recipes_search` (Spoonacular mocked), `test_food_barcode`
  (OpenFoodFacts mocked), `test_weather_current` (Open-Meteo
  mocked), `test_websocket_origin_reject`. Goal: every router has
  one happy-path test + the one explicit security check
  (origin-rejection). Not coverage — wiring proof.
- A request to any route emits exactly one structured log line at
  completion carrying `request_id`, `method`, `path`, `status`,
  `latency_ms`. Inspecting the same line for an external-API proxy
  call also shows the nested upstream-client log carrying the same
  `request_id`.
- `uv run pytest` green for all tests that don't require an external
  bot.
- `uv run uvicorn app.main:app` starts cleanly locally.
- `curl http://localhost:8000/api/v1/health` → 200.
- `curl http://localhost:8000/api/v1/openapi.json` returns the schema
  and every route in it lives under `/api/v1/*`.
- Manual: `GET /api/v1/stocks/AAPL` returns a `Stock` payload sourced
  from Finnhub (not yfinance — verify by inspecting the client log
  line).
- Manual: `GET /api/v1/recipes/search?q=pizza` returns Spoonacular
  results; `GET /api/v1/recipes/search?q=biryani` includes
  TheMealDB-augmented results in the same envelope.
- Manual: `GET /api/v1/food/barcode/3017620422003` (Nutella) returns
  product data from OpenFoodFacts.
- Manual: `GET /api/v1/weather/current?lat=47.6&lon=-122.3` returns
  current Seattle conditions from Open-Meteo;
  `GET /api/v1/weather/forecast?lat=47.6&lon=-122.3&days=3` returns
  a 3-day forecast.
- Manual: POST a HMAC-signed payload to
  `/api/v1/internal/discord/incoming` (signature per Issue K),
  observe fan-out to a connected WS client.
- Manual: open a WS connection without an allowed `Origin` header,
  observe handshake rejection (Issue E layer 1).
- Inspect a structured log line for any upstream call and verify it
  carries `provider`, `path`, `status`, `latency_ms` per the
  `app/clients/_base.py` convention.

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
