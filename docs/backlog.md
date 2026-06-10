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
- **Caching for external-API proxies.** Stocks (Finnhub), recipes
  (Spoonacular + TheMealDB), food (OpenFoodFacts), and weather
  (Open-Meteo) all hit rate-limited upstreams and return cache-friendly
  data. Start with an in-process TTL cache; graduate to Redis if
  multi-replica. TTL guidance per surface: stocks quote ~30s, stocks
  fundamentals ~1h, recipes search ~24h, OFF barcode ~7d, weather
  current ~10min, weather forecast ~1h.

## Medium-term

- **Rate limiting on external-API proxies.** `slowapi` is the standard
  FastAPI integration. Decided 2026-06-09: deferred from the
  modernization. Adds in-memory-or-Redis state, complicates testing,
  and the upstream rate limits (Finnhub 60/min, Open-Meteo 10k/day)
  are the real ceiling anyway. Revisit if/when an external-API proxy
  gets hammered.
- **Token strategy upgrade.** Current is 24h HS256 JWT, no refresh,
  no revocation. Decided 2026-06-09: keep as-is through cutover.
  Refresh tokens / revocation lists carry real cost (rotation logic,
  DB or Redis state for revocation, client-side refresh handling)
  and the single-user playground doesn't justify them. Revisit when
  there's a real user base.
- **Test suite expansion beyond smoke tests.** Modernization lands
  smoke tests only — one happy-path per router + WS origin-reject
  (substep 3 acceptance). Expand to: property tests for the
  upstream-response normalizers in `app/clients/*`, fuzz the HMAC
  contract on `/internal/discord/incoming`, contract test that runs
  the SPA's openapi codegen against a fresh schema and diffs against
  a committed snapshot.

## External-API proxy expansion (from 2026-06-09 research)

Picks from the research shortlist that did **not** make the
modernization cutover. Each is independent and standalone. Background
detail in `~/research/2026-06-09-free-public-apis/REPORT.md` and the
per-bucket `scout-NN-*.md` files. Order is rough priority.

- **Finnhub extensions.** The substep-3 swap uses Finnhub for quote /
  profile / candles only. Finnhub also exposes a news endpoint and a
  WebSocket trades stream — both are real extensions to `/stocks/*`
  with no extra dependency.
- **Open-Meteo extensions (AQI + marine + historical + geocoding).**
  The substep-3 cutover ships `/weather/current` + `/weather/forecast`
  on raw lat/lon. Open-Meteo has zero-auth sibling APIs for air
  quality, marine, and ERA5 historical (back to 1940) at the same
  keyless surface. Pair with a geocoding upstream (LocationIQ free key
  or keyless Nominatim — 1 req/sec, mandatory caching) so the weather
  endpoints accept city names. Becomes a `/weather/*` + `/location/*`
  cluster.
- **Random-content bot cluster — JokeAPI + Open Trivia DB + Quotable.**
  Three keyless APIs covering jokes / trivia / quotes; powers a bot
  `/random/{joke|trivia|quote}` cluster (and matching SPA widgets).
  Strong filtering on JokeAPI (safe-mode, category) and OTDB
  (category, difficulty). Low effort per, medium to unify response
  shapes per the uniform-surface principle.
- **Daily-content visual surface — Met Museum + NASA APOD.** Two
  keyless APIs for art + space daily content. No current visual
  editorial on the SPA — high novelty/low effort. Could land as
  `/daily/{art|space}` with a sensible default-cache TTL (24h).
- **Tabletop / fandom trio — PokeAPI + Scryfall + D&D 5e SRD.** Three
  keyless fandom APIs covering Pokémon, MTG, and D&D references.
  Strong bot fit (`!card <name>`, `!pokemon <name>`, `!spell <name>`)
  and reasonable SPA fit. Unify under `/fandom/{domain}/{query}` if
  taking them together.
- **FRED macro time-series.** ~800k macro / economic time-series from
  the St. Louis Fed. Government-grade stability, free key, 120
  req/min. Unique surface — no other free API covers this. Natural
  pair with the existing `/stocks` cluster as `/macro/*`. Verify the
  rate-limit claim against official docs (research scouts disagreed
  on whether the limit is 120/min or absent).
- **Utility pair — Frankfurter + Nager.Date.** Keyless currency
  conversion (Frankfurter) + keyless public-holidays per country
  (Nager.Date). Trivial integration, zero rate-limit concerns. Land
  together as `/utility/currency` + `/utility/holidays`.
- **News / feeds cluster — HN + DEV.to + Mastodon + arXiv + Currents.**
  Bot-command surface (`!hn`, `!arxiv <topic>`) + SPA feed widgets.
  All keyless or free-key with commercial-OK terms. Currents API is
  the proper news-aggregator slot since NewsAPI / GNews have
  dev/localhost-only clauses. Reddit deliberately excluded (OAuth
  + commercial-forbidden post-2023; flag risk if revisited).
- **Census / demographics — US Census + FRED + World Bank Indicators.**
  SPA data-viz surface. Time-series friendly, geo-aggregation down
  to county level. Heavier lift to design a useful response shape;
  defer until a concrete SPA experiment motivates it.

## Open / strategic

- **External API viability — decided 2026-06-09 (revised same day
  after research landed).** yfinance is being **replaced** (not just
  kept) by Finnhub during substep 3 — the modernization is the right
  window to swap upstreams rather than carry the Yahoo-scraper
  fragility forward. Spoonacular stays as primary recipes upstream
  but moves off RapidAPI to direct `api.spoonacular.com`, and gets
  two keyless complements layered in: TheMealDB (ethnic-cuisine
  augmentation) and OpenFoodFacts (sibling `/food/barcode/{barcode}`
  endpoint). See `docs/modernization-plan.md` substep 3 for execution
  detail.
- **External-API expansion — research output 2026-06-09.** Eleven-
  scout broad survey of free public APIs landed at
  `~/research/2026-06-09-free-public-apis/` (REPORT.md is the
  entry point; per-bucket detail in `scout-NN-*.md`, cross-cutting
  synthesis in `organized.md`). Three picks land in the modernization
  cutover (Finnhub, OpenFoodFacts + TheMealDB, Open-Meteo as the
  one new endpoint cluster). The rest are filed as backlog items
  below. A narrower deeper second research pass may be queued later;
  not committed yet.
- **Uniform external-API surface (design principle).** bniehuser-api
  endpoints should present a stable, uniform request/response/error
  shape regardless of upstream provider. Multiple complementary
  upstreams may be layered behind a single bniehuser endpoint
  (e.g. recipes = Spoonacular + TheMealDB + OpenFoodFacts). Shared
  client conventions (error normalization, timeouts, structured logs)
  preferred over per-endpoint ad-hoc httpx. The free-API research
  output is filtered through this lens — providers that *compose*
  with the existing surface beat providers that are merely "best in
  isolation".
- **New feature surface.** This backend is intentionally a playground.
  File new feature ideas here as they come up — they don't block
  cutover.
