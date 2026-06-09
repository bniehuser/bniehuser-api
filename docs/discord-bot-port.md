# Discord bot — port notes for hub-bot

The legacy in-repo Discord bot is parked under `legacy/discord-bot/`
during the 2026 modernization (parked in substep 1, deleted in
substep 4). This doc captures the intent so the eventual
`bniehuser/hub-bot` service inherits the same behavior faithfully.

## Files preserved

- `legacy/discord-bot/bot_daemon.py` — `discord.py` 1.7.2 process.
  Out of date but illustrates the runtime model.
- `legacy/discord-bot/messaging.py` — `SocketMessage` shape +
  `SocketScope` / `SocketSource` enums and JSON codec.

## Behavioral contract (port faithfully)

### Channel + DM routing

- Bot is configured against one Discord channel (`DISCORD_CHANNEL`) and
  one owner user (`DISCORD_OWNER_SNOWFLAKE_ID`).
- **chat → Discord:**
  - `SocketScope.PUBLIC` from a non-BOT source → send to configured
    channel as `#{sender}: {message}`.
  - `SocketScope.PRIVATE` → DM to owner as `#{sender}: {message}`.
  - `SocketScope.SYSTEM` → not forwarded.
- **Discord → chat:**
  - Any non-bot message in the configured channel that doesn't start
    with the command prefix becomes a `SocketMessage(source=BOT,
    sender=author.name, message=content)`.
  - If the Discord message is a reply to a previous bot-forwarded
    message, the reply's recipient is parsed from the prefix
    (`#<sender>:` regex) and set on the outgoing `SocketMessage`.

### Command prefix and built-in commands

- Activator: `~`.
- Built-in commands:
  - `~hello` — random greeting from a small pool.
  - `~words` — `:flying_saucer: KLAATU BARADA NIKTO`.
  - `~help [command]` — custom embed-based help. The default
    `discord.py` help command is explicitly disabled in favor of this.
- Owner identification: `bot.application_info().owner`, cached on
  `on_ready`.

### Runtime model (legacy)

- The legacy bot ran as its own process under supervisord, connected
  back to the api's `/ws/bot` endpoint via `websocket-client`, and
  bridged Discord ↔ ws in both directions.

### Runtime model (hub-bot — what to build)

- hub-bot is the always-on Discord client, running in a separate
  container under infra's supervision.
- The api exposes `/api/v1/internal/discord/incoming` (HMAC-verified
  inbound from hub-bot — see `PROJECT.md` Issue K for the contract).
- The api exposes a `discord_outbound(scope, message)` helper that
  POSTs to `http://hub-bot:9000/send` with `Authorization: Bearer
  $BOT_API_TOKEN`.
- hub-bot consumes the outbound POSTs and translates them back into
  Discord channel sends / DMs per the routing rules above.

## Things to actively *not* port

- The dual `websockets` + `websocket-client` import (only one was used).
- The module-level `loop = asyncio.get_event_loop()` grab — legal in
  3.8, deprecated in 3.10+.
- Hardcoded command prefix `~` in code — make it an env / config item.
- `print()`-based logging.

## Things to add while porting

- Reconnection on websocket / Discord gateway drop (the legacy bot
  died on disconnect with no retry).
- Structured logging (match the api's `structlog` choice).
- A `/health` endpoint on the bot side too, for hub supervision.
- `discord.py` 2.x patterns: `Bot(intents=...)`, slash commands or
  message-content intent declared explicitly, modern `setup_hook`
  lifecycle rather than `loop.add_signal_handler` setup.
