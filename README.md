# Enfilera

**English** · [Português (Brasil)](README.pt-BR.md)

**Is the cafeteria line worth walking over for right now, or should I wait?**

Enfilera is a Telegram bot that crowdsources how long the queue at a
university cafeteria (*bandejão*) actually takes. Students start a timer when
they join a line and stop it at the turnstile; the bot turns those anonymous
transit times into a single live estimate per line — "~12 min" — so the next
person knows whether to go now or come back later.

Separate estimates for each line (card / pix / …). No accounts, no tracking,
no stored location.

## Quickstart

```bash
uv sync                                              # install dependencies
cp config/config.example.toml config/config.toml     # then edit for your cafeteria
export ENFILERA_BOT_TOKEN=...                         # bot token from @BotFather
uv run python -m enfilera                             # start the bot
```

The SQLite database is created on first run (`enfilera.db` by default; override
with `ENFILERA_DB`, and the config path with `ENFILERA_CONFIG`). Run the test
suite with `uv run pytest`.

## Fork it for your cafeteria

Enfilera is built to be forked: point it at *your* restaurant by editing one
config file — lines, operating periods, geofence center/radius — and
deploying. Every cafeteria-specific value lives in `config/config.toml`;
nothing is hardcoded. See [`docs/`](docs/) for the fork + deploy guide.

## How it works

The estimation algorithm, the anti-abuse model, and the full roadmap live in
[`docs/PLAN.md`](docs/PLAN.md).
