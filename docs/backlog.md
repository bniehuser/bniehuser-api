# Backlog — beyond the 2026 cutover

Items deferred from the modernization plan. Each one stands alone and
can be picked up after `modernize-2026` merges to `main`. Order within
sections is rough priority.

## Near-term

- **Email sender for password reset.** Wire SES (or alternative) and
  flip `/api/v1/password-recovery/{email}` from 501 to functional.
  `app/auth/tokens.py` already produces / verifies tokens; only the
  send leg is missing. See `PROJECT.md` Issue L.
- **SPA codegen → OpenAPI 3.1.** Modernization pins
  `FastAPI(openapi_version="3.0.2")` (Issue B) so the SPA's existing
  `openapi-typescript-codegen` keeps working. Evaluate alternatives
  that handle 3.1's nullable shape: `@hey-api/openapi-ts`,
  `openapi-typescript` + `openapi-fetch`, or `orval`. Swap in the SPA
  repo, then drop the `openapi_version` pin here.
- **Websocket auth layer 2 — `VITE_WS_TOKEN`.** Static token baked
  into the SPA build, appended as `?token=` on the WS URL, validated
  server-side. Adds infra-side scope: SSM → CF Pages env-var pipeline.
  Flag in `~/code/barry/infra/PROJECT.md` when starting.
- **Caching for external-API proxies.** Stocks (yfinance) and recipes
  (Spoonacular) both hit rate-limited upstreams and return
  cache-friendly data. Start with an in-process TTL cache; graduate
  to Redis if multi-replica.
- **Request logging middleware.** `structlog` will be in the dep list
  but the modernization doesn't wire it. Add: startup config + ASGI
  middleware emitting `{request_id, method, path, status, latency_ms}`
  per request.

## Medium-term

- **User model expansion.** Add `created_at`, `updated_at`,
  `last_login`. Trivial migration if folded into the substep 2
  baseline; an annoying separate migration later.
- **Rate limiting on external-API proxies.** `slowapi` is the standard
  FastAPI integration.
- **Token strategy upgrade.** Current is 24h HS256 JWT, no refresh,
  no revocation. Fine for the playground; revisit if/when more users.
- **Test suite.** `tests/conftest.py` exists but is empty. Substep
  acceptance criteria reference `uv run pytest`. Decide a test
  strategy (httpx `AsyncClient` against the app + a throwaway
  postgres via testcontainers or a session-scoped fixture).

## Open / strategic

- **External API viability.** yfinance is chronically fragile (Yahoo
  scraping breaks every few months), and RapidAPI Spoonacular's free
  tier is ~50 req/day with a direct `api.spoonacular.com` alternative
  that's a cleaner integration if you're not using other RapidAPI
  services. Re-evaluate whether to keep, replace, or scope-cut these
  endpoints once usage signal is clearer.
- **New feature surface.** This backend is intentionally a playground.
  File new feature ideas here as they come up — they don't block
  cutover.
