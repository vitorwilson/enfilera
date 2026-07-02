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
config file — lines, operating periods, geofence center/radius — and deploy
with one command that runs the same on a Raspberry Pi, a VPS, or your laptop.

```bash
cp config/config.example.toml config/config.toml     # 1. copy the config
cp config/enfilera.env.example config/enfilera.env   # 2. copy the env file
```

Now **edit both** before deploying — they ship with placeholder values, and the
fake bot token alone will stop the bot from starting:

- `config/config.toml` — your lines, operating periods, timezone, geofence, and
  `admin_ids`. Every cafeteria-specific value lives here; nothing is hardcoded.
- `config/enfilera.env` — paste the real bot token from
  [@BotFather](https://t.me/BotFather).

```bash
bin/deploy                                           # 3. docker compose up -d --build
```

The database directory and its ownership are handled on first run — no manual
setup on any host. See [`docs/DEPLOY.md`](docs/DEPLOY.md) for remote deploys,
operating, and database backup/restore.

## How it works

The estimation algorithm, the anti-abuse model, and the full roadmap live in
[`docs/PLAN.md`](docs/PLAN.md).
