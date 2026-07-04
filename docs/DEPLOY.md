# Deploy & fork Enfilera

Point Enfilera at *your* cafeteria and run it anywhere Docker runs — a
Raspberry Pi, a VPS, or a spare laptop. Deployment is one entrypoint
(`bin/deploy`) wrapping Docker Compose, so the same command works on every
host and the bot supervises itself.

## 1. Fork it for your cafeteria

Everything cafeteria-specific lives in one file; nothing is hardcoded.

```bash
cp config/config.example.toml config/config.toml
```

Edit `config/config.toml` for your installation — the example is fully
commented. The values you will change:

- **`[restaurant]`** — `timezone`, and the geofence `latitude` / `longitude` /
  `radius_m` (the timer only starts within this radius; the location is checked
  and then discarded, never stored).
- **`[schedule]`** — `operating_days` (ISO weekdays) and the `[[schedule.periods]]`
  windows (e.g. lunch / dinner). `id` is stable and is what a closure targets.
- **`[[lines]]`** — your queues (card / pix / …). `id` is stored; `label` is
  shown to users.
- **`[bot]`** — `admin_ids` (the Telegram user IDs allowed to run the operator
  commands), `issues_url`, `author_url`, and the flood limits.
- **`[estimation]`** / **`[retention]`** — tune only if you need to.

## 2. Get a bot token

Create a bot with [@BotFather](https://t.me/BotFather) and copy its token.
Provide it through the gitignored runtime env file (read by Compose):

```bash
cp config/enfilera.env.example config/enfilera.env
# edit config/enfilera.env and paste your real ENFILERA_BOT_TOKEN
```

The variable name must match `[bot].token_env` in your config (default
`ENFILERA_BOT_TOKEN`). The token never goes in the config file or the image.

## 3. Deploy

On the machine that will run the bot:

```bash
bin/deploy
```

That builds the image and starts the service with `docker compose up -d
--build`. `restart: unless-stopped` brings the bot back after a crash or a host
reboot, unattended — there is no systemd to configure.

The bot process runs as a non-root user (UID 1000). On the first start the
container is briefly root only to fix the owner of the bind-mounted `data/`
directory — a rootful Docker host creates a missing bind source as `root:root`
— then drops to that user before running the bot. So the database is writable
on any host, whatever your login UID, with no manual `chown`.

### Deploy to a remote host

The simplest, most portable way is to run `bin/deploy` **on** the host that
will run the bot. SSH in, put the repo and your config there once, then deploy
(and re-deploy) with a pull:

```bash
ssh pi@raspberrypi.local
git clone https://github.com/your-username/enfilera.git && cd enfilera
cp config/config.example.toml config/config.toml     # edit for your cafeteria
cp config/enfilera.env.example config/enfilera.env   # add your token
bin/deploy
# later, to ship an update:
git pull && bin/deploy
```

The host needs Docker, Git, and SSH access; nothing else (no Python, no uv).

> Advanced: you can also drive a remote Docker daemon from your laptop with
> `DOCKER_HOST=ssh://pi@host bin/deploy` (or a `docker context`). The image
> build streams over SSH, but the bind-mounted `config/` and `data/` then
> resolve on the **remote** host's filesystem — so the repo and config still
> need to live there. Running `bin/deploy` on the host, as above, keeps that
> simple.

## 4. Operate

```bash
docker compose logs -f          # follow the structured logs
docker compose ps               # is it up?
docker compose restart          # restart
bin/deploy                      # ship an update (rebuild + restart)
```

Operator controls live in the bot itself (admin-only Telegram commands):
`/status`, `/pausar` · `/retomar`, and the closure commands `/fechar` ·
`/fechamentos` · `/reabrir`.

## 5. Back up & restore the database

All dynamic state — samples, per-user submissions, closures, the halt flag —
lives in a single SQLite file on the host at **`data/enfilera.db`** (a mounted
volume). The pruning job keeps it bounded, so it stays small.

**Backups are automatic.** `docker compose up` starts a `backup` sidecar that
writes a consistent snapshot to **`backups/`** once a day and keeps the most
recent `[backup].keep` (default 30), deleting older ones. It uses SQLite's online
backup, so the bot keeps serving during a snapshot — no downtime, no manual
`cp`, no host cron. Snapshots are named `enfilera-YYYYMMDD-HHMMSS.db`:

```bash
docker compose logs -f backup     # watch the daily snapshot
ls -1 backups/                    # the rotation, newest last
```

**Back up on demand** — e.g. right before a risky migration:

```bash
docker compose run --rm backup python -m enfilera.backup
```

**Copy the snapshots off the Pi.** An SD card is a single point of failure, so
on-Pi snapshots alone are not enough. Pull `backups/` to another machine you
control — nothing to install on the Pi. From that other machine:

```bash
rsync -az --exclude=.gitkeep \
  pi@raspberrypi.local:enfilera/backups/ ~/enfilera-backups/
```

Deliberately **no `--delete`**: the copy *accumulates* snapshots and keeps them
after the Pi rotates them out of its `keep` window, so the off-site archive
outlives the Pi. Snapshots are tens of KB, so it never meaningfully grows.

**Schedule the pull.** On an always-on host, a cron entry is fine. On a laptop —
which sleeps through cron's scheduled minute and never runs it — use a systemd
**user** timer with `Persistent=true`, which runs a missed pull on the next wake.
Two files under `~/.config/systemd/user/` (replace the host and the paths):

```ini
# enfilera-pull.service
[Unit]
Description=Pull Enfilera DB snapshots off the Pi
Wants=network-online.target
After=network-online.target

[Service]
Type=oneshot
ExecStart=/usr/bin/rsync -az --exclude=.gitkeep -e '/usr/bin/ssh -o BatchMode=yes -o ConnectTimeout=10' pi@raspberrypi.local:enfilera/backups/ %h/enfilera-backups/
```

```ini
# enfilera-pull.timer
[Unit]
Description=Pull Enfilera backups periodically

[Timer]
OnCalendar=*-*-* 00/6:17:00
Persistent=true
RandomizedDelaySec=120

[Install]
WantedBy=timers.target
```

```bash
systemctl --user enable --now enfilera-pull.timer
loginctl enable-linger "$USER"   # keep the timer running while logged out
```

The SSH key must be passphrase-free (or agent-backed) so the pull runs headless.

**Restore:** stop the bot, copy a chosen snapshot over the live DB, start again.

```bash
docker compose stop
cp backups/enfilera-20260704-210500.db data/enfilera.db
docker compose start
```

## 6. Keep the database bounded (pruning)

This is automatic: `docker compose up` starts a `prune` sidecar alongside the
bot that drops samples past the retention window (default 30 days) and
already-past closures once a day, so the SQLite file stays bounded with no host
cron to remember. It reuses the bot's image, config, and `data/` volume, and
logs each run's counts as one JSON line:

```bash
docker compose logs -f prune    # watch the daily prune
```

To prune on demand (e.g. right after a big purge), run it once yourself:

```bash
docker compose run --rm enfilera python -m enfilera.prune
```

## 7. Cut a release

Releases are triggered by a version tag, never by hand:

1. Move the `## [Unreleased]` entries in `CHANGELOG.md` under a new
   `## [X.Y.Z]` heading (Keep a Changelog format).
2. Bump `__version__` in `src/enfilera/__init__.py`.
3. Commit, then tag and push:

   ```bash
   git tag vX.Y.Z && git push origin vX.Y.Z
   ```

The release workflow builds the wheel + sdist once and publishes a GitHub
Release whose body is that version's changelog section (extracted by
`bin/changelog-section`).

## Bare-metal alternative

Docker is the supported default, but Enfilera is a plain `python -m enfilera`
process: any supervisor (systemd, supervisord, a process manager) can run it
directly, given the dependencies installed (`uv sync --no-dev`), the token in
the environment, and `config/config.toml` present. The container path exists so
you don't have to.
