# Active project: bniehuser-api modernization

Bring this 2021-era FastAPI + Python 3.8 codebase to current stack so it
can deploy as the first python-app tenant of `hub-python` on the hub. Six
sequential passes on a `modernize-2026` branch; PR to `main` when SPA
round-trips green.

## Substeps

1. **Tooling baseline** — replace Poetry with `uv`, pin Python 3.12, add
   ruff/pyright/Justfile, drop dead deps. Park the legacy in-repo Discord
   bot to `legacy/discord-bot/` (drops it from runtime, preserves code;
   intent captured in `docs/discord-bot-port.md`). Delete unused
   `app/external_api/fio_rest.yaml`. No api-runtime behavior change.
2. **Data layer rewrite** — collapse the 5-file SQLAlchemy layer to
   `app/db.py` + `app/models/user.py` + `app/crud/user.py`. Async
   `AsyncSession` per Issue J. Alembic async-template baseline. DB
   URL composed from libpq env vars per Issue H.
3. **FastAPI / Pydantic v2 cascade** — lifespan replaces on_event;
   pydantic_settings; pyjwt replaces python-jose; bcrypt replaces passlib;
   `@model_validator(mode='before')` for stocks/recipes PascalCase remap;
   websocket gains `/internal/discord/incoming` HMAC endpoint + outbound
   helper that posts to `http://hub-bot:9000/send`.
4. **Bot code cleanup** — delete `legacy/discord-bot/` and
   `docs/discord-bot-port.md` (parked / authored in substep 1). Gated
   on infra `hub-bot` substack having been applied on the hub (so the
   external `hub-bot:9000` service exists). Pure deletion pass — no
   new behavior.
5. **Dev runtime** — `docker-compose.yml` for local dev (api + postgres +
   bot). **No production Dockerfile** — hub-python bind-mounts source and
   runs `uv sync` at container start (see infra D1). `.hooks/deploy.sh`
   committed alongside source.
6. **SPA round-trip verification** — `pnpm codegen` in
   `~/code/barry/bniehuser/react/` against new local api; confirm
   RecipesService, StocksService, websocket bridge all work; file
   issues for any SPA-side breakage from openapi shape changes.

## Completion criteria (gating items for infra `hub-python` cutover)

Infra's `hub-python` substack (PROJECT.md substep 1 in
`~/code/barry/infra/`) **applies regardless of this repo's state** — a
non-compliant tenant just crash-loops its supervisord program harmlessly.
The smoke step of infra substep 2 is what needs this repo's `main`
branch to satisfy:

- [ ] `pyproject.toml` (uv-managed) with: fastapi, uvicorn[standard],
  sqlmodel, psycopg[binary], pyjwt, bcrypt, httpx, structlog, alembic,
  python-multipart, pydantic-settings.
- [ ] `uv.lock` committed.
- [ ] `app/main.py` exporting `app: FastAPI` (matches infra's catalog
  `serve: "uv run uvicorn app.main:app --host 0.0.0.0 --port $HTTP_PORT"`).
- [ ] HTTP server binds to `$HTTP_PORT` — handled by the catalog's
  `serve:` command above (uvicorn picks up `--port $HTTP_PORT`); no
  action needed in app code.
- [ ] Postgres connection composed from `PG{HOST,PORT,USER,PASSWORD,DATABASE}`
  libpq env vars (see Issue H below). **Not `DATABASE_URL`.**
- [ ] Named secrets read from env vars matching the catalog's
  `needs.secrets[]` list: `SECRET_KEY`, `FORWARD_HMAC_SECRET`,
  `BOT_API_TOKEN`, `BOOTSTRAP_USER_EMAIL`, `BOOTSTRAP_USER_PASSWORD`,
  `FINNHUB_API_KEY`, `SPOONACULAR_API_KEY`. One env var per name.
  **Cross-repo signal:** the post-2026-06-09 external-API decisions
  (Finnhub replaces yfinance, Spoonacular direct replaces RapidAPI)
  add `FINNHUB_API_KEY` + `SPOONACULAR_API_KEY` and retire
  `RAPIDAPI_KEY`. Infra catalog `needs.secrets[]` for the api program
  must update to match before this gate item can flip green. Keyless
  upstreams added in the same window (OpenFoodFacts, TheMealDB,
  Open-Meteo) need no catalog change.

**Out of scope for cutover:**

- `/health` route — useful as a no-auth liveness probe for SPA /
  uptime checks, but not a cutover gate (infra deferred fleet-wide
  health checks).
- `.hooks/deploy.sh` — infra owns the deploy action entirely
  (`git pull --ff-only && docker exec python supervisorctl restart api`).
  No `.hooks/` directory in the tenant repo.

When this list is green on `main`, signal the infra session with "api
ready." Infra resumes from `docs/hub-python-substack.md` Substep 2
(apply chain → smoke → push-to-deploy round-trip).

Minimum to meet the gate: substep 1 (tooling + uv deps) + substep 2
(libpq env wiring). Substeps 3-6 can continue after the initial cutover —
the api will respond to whatever endpoints have been ported by then;
incomplete endpoints just 404/500 until they ship.

## How the repo is organized

- `PROJECT.md` (this file) — project plan + completion criteria.
- `docs/modernization-plan.md` — pass-by-pass execution detail.
- `docs/discord-bot-port.md` — behavioral contract for the eventual
  hub-bot extraction (created in substep 1, deleted in substep 4).
- `docs/backlog.md` — items deferred beyond the modernization cutover.
- `app/` — application code (Python).
- `legacy/discord-bot/` (substep 1 → 4) — parked legacy bot code, not
  in the runtime path.
- `tests/` — pytest suite.
- `pyproject.toml` + `uv.lock` (post substep 1) — declared deps.

Legacy 2021 files (`poetry.lock`, the Poetry `pyproject.toml`,
`supervisord.conf`, `.idea/`, `app/external_api/fio_rest.yaml`) get
removed in substep 1.

## Cross-cutting decisions

### Stack picks (precedent for this and future python work)

- **Package manager:** `uv`. `pyproject.toml` + `uv.lock`. No
  `requirements.txt`.
- **Python:** 3.12 pinned (`.python-version`).
- **Lint+format:** `ruff`. **Type checker:** `pyright`.
- **Web framework:** FastAPI 0.115+. SPA codegen against
  `/api/v1/openapi.json` is load-bearing.
- **ORM:** SQLModel (pydantic + SQLAlchemy 2 unified). Single class for
  DB + API model.
- **Migrations:** Alembic, baseline from SQLModel metadata.
- **DB driver:** `psycopg` v3.
- **Auth:** `bcrypt` 4.x direct + `pyjwt`. Drop `passlib` (bcrypt 4
  compat hell) and `python-jose` (unmaintained).
- **HTTP client:** `httpx`.
- **Logging:** `structlog` JSON output.
- **Discord client:** out of scope here — moved to hub-bot service.
- **Local dev:** `docker compose` + `Justfile`.

### Issue B — FastAPI OpenAPI version pin (decided: 3.0.2)

Pin `FastAPI(openapi_version="3.0.2")` in substep 3. FastAPI 0.115+
emits OpenAPI 3.1 by default but the SPA's existing
`openapi-typescript-codegen` does not handle 3.1's nullable shape
cleanly. Followup in `docs/backlog.md`: swap the SPA's codegen tool
for a 3.1-aware one, then drop this pin.

### Issue D — websocket connections dict

Legacy `websocket.py:14` declares `connections: Dict[str, WebSocket] = {}`
as class-level attribute — shared mutable default. Use instance attr in
substep 3 rewrite.

### Issue E — `/ws/{client_id}` auth (layer 1 in modernization; layer 2 backlog)

Substep 3 ships **Origin-check only**: reject WS upgrade unless
`Origin` matches `https://bniehuser.com` or a localhost dev origin.
This deliberately avoids any infra-side change during the
modernization pass.

Layer 2 (static `VITE_WS_TOKEN` baked into the SPA build, appended as
`?token=…` on the WS URL, validated server-side) is filed in
`docs/backlog.md`. It adds SSM→CF Pages env-var pipeline scope on the
infra side — flag in `~/code/barry/infra/PROJECT.md` when starting.

Layer 3 (ticket-issuing endpoint) deferred indefinitely.

### Issue H — postgres connection via libpq env vars (not `DATABASE_URL`)

Infra contract D7: hub-python injects `PG{HOST,PORT,USER,PASSWORD,DATABASE}`
into the supervisord program env, **not** a `DATABASE_URL`. Tenant
assembles its own URL. Rationale: libpq tools (psql, pg_dump) work
without flags, and SQLAlchemy/Django/raw psycopg all assemble fine.

Practical shape in `app/core/config.py`:

```python
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    PGHOST: str = "localhost"
    PGPORT: int = 5432
    PGUSER: str = "postgres"
    PGPASSWORD: str = ""
    PGDATABASE: str = "api"

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+psycopg://{self.PGUSER}:{self.PGPASSWORD}"
            f"@{self.PGHOST}:{self.PGPORT}/{self.PGDATABASE}"
        )
```

`app/db.py` uses `create_async_engine(settings.database_url, …)` —
`psycopg` v3 supports async over the same `postgresql+psycopg://...`
URL scheme, so this composition is unchanged by the async-session
choice (Issue J). Local dev `.env` carries the same `PG*` vars so the
same code path works under `docker compose up` (substep 5).

### Q6 — auth bootstrap via app lifespan

Idempotent `create_superuser_if_missing()` called from the `lifespan`
startup hook in `app/main.py`. Reads `BOOTSTRAP_USER_EMAIL` /
`BOOTSTRAP_USER_PASSWORD` from env (SSM-sourced on hub, present in the
supervisord program's env at startup). No-ops if the user already exists.

**Why lifespan, not `docker exec`:** post-shared-container refactor
(infra 2026-06-09), there's no `api` container — the shared `python`
container runs supervisord. `docker exec python …` doesn't inherit the
per-program supervisord env (`BOOTSTRAP_USER_*`, `PG*`), so a one-shot
CLI command would need explicit env passthrough. Lifespan-startup
side-steps that: the api process already has the env, runs the bootstrap
once per restart, idempotent.

`USERS_OPEN_REGISTRATION` stays false until a SPA login flow lands.

### Issue I — API routing prefix (decided: `/api/v1`)

Substep 3 mounts the `api_router` with `prefix="/api/v1"` in
`app/main.py`. All routes therefore live under `/api/v1/*`.
`OAuth2PasswordBearer(tokenUrl="/api/v1/login/access-token")` matches.

Why: aligns with the openapi.json URL (`/api/v1/openapi.json`),
signals versioning as a namespace (no plan to maintain multiple
versions in parallel), costs one line. The SPA picks up the new
paths via codegen in substep 6 — expect a testing window where the
SPA against the new backend is broken until codegen reruns.

### Issue J — Database session strategy (decided: async)

`app/db.py` builds an async engine via
`sqlalchemy.ext.asyncio.create_async_engine` and a session factory
yielding `sqlmodel.ext.asyncio.session.AsyncSession`. `psycopg` v3
supports async over the same URL scheme (`postgresql+psycopg://...`),
so Issue H's composition is unchanged.

All endpoints that touch the DB become `async def` with `await
session.exec(select(...))`. CRUD helpers in `app/crud/user.py` are
async. Alembic uses the async template
(`alembic init --template async migrations`).

Why: traffic doesn't require async; this is a deliberate exploration
of async patterns at small scope to inform the async-stack work
happening on a parallel work project.

### Issue K — `/internal/discord/incoming` HMAC contract (decided)

Full path: `POST /api/v1/internal/discord/incoming`.

Required headers:
- `X-Forward-Timestamp: <unix-epoch-seconds>`
- `X-Forward-Signature: sha256=<hex digest>`

Signature input:
```
hmac.new(FORWARD_HMAC_SECRET.encode(),
         f"{timestamp}.{request_body}".encode(),
         hashlib.sha256).hexdigest()
```

Reject if `abs(now - timestamp) > 300` (replay protection).

Body:
```json
{"scope": "public" | "private", "sender": "string", "message": "string"}
```

On accept, fan out to connected `/api/v1/ws/{client_id}` clients per
the PUBLIC/PRIVATE rules captured in `docs/discord-bot-port.md`.
hub-bot must produce matching signatures — capture this contract in
`~/code/barry/infra/PROJECT.md` when hub-bot work starts.

### Issue L — Password reset behavior (partial functional)

- `app/auth/tokens.py` holds `generate_password_reset_token` /
  `verify_password_reset_token`, rewritten on `pyjwt`. Replaces the
  legacy `app/utils.py` (deleted in substep 3).
- `POST /api/v1/reset-password/` — functional once substep 3 ships:
  takes token + new password, verifies, updates user. No email needed.
- `POST /api/v1/password-recovery/{email}` — returns **501 Not
  Implemented** until an email sender is wired (backlog item). Looks
  up the user, generates the token server-side (exercise the code
  path), then 501s. **Must not return the token in the response body**
  — the legacy code did, which is a credential-leak shape.

### Q8 — SPA `VITE_API_URL` already set

`bniehuser-com-web` has `VITE_API_URL: https://api.bniehuser.com` in
infra's `sites.yaml`. CF Pages env changes don't auto-redeploy. **Before
declaring cutover green:** trigger a CF Pages redeploy or verify the
last deploy timestamp post-dates the env var addition.

## External coordination (not owned by this repo)

- **`~/code/barry/infra/`** — owns the `hub-python` substack and the api
  catalog entry. Apply gate items (above) ship to this repo's `main`,
  user signals "api ready" in the infra session, infra applies. See
  `infra/docs/hub-python-substack.md`.
- **`~/code/barry/bniehuser/react/`** — SPA. Consumes api openapi
  codegen (substep 6). Any breakage from new openapi shape is SPA-side
  fixup, tracked there.
- **(future) `bniehuser/hub-bot` repo** — bot's eventual home (infra
  PROJECT.md substep 3). This repo doesn't touch bot code beyond
  deleting it in substep 4.

## Status

| # | Substep | Status |
|---|---|---|
| 1 | Tooling baseline | not started |
| 2 | Data layer rewrite | not started |
| 3 | FastAPI / Pydantic v2 cascade | not started |
| 4 | Bot code cleanup | blocked on infra hub-bot apply |
| 5 | Dev runtime | not started |
| 6 | SPA round-trip verification | not started |
| — | Completion criteria for cutover | blocked on substep 1 |
