# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.5] - 2026-07-15

### Changed
- The "how's the line" reply (`/agora`) now shows **"sem registro"** when no
  real data backs a line's estimate — no admitted samples today, no previous
  block, and no historical baseline — and nudges the user to contribute the
  first sample. Previously it showed the configured seed (`~1 min`), which was
  indistinguishable from a genuine 1-minute wait (a real one exists in the
  data) and misled users. The fresh-fork bootstrap now reads "sem registro"
  everywhere until real samples arrive.
- The lower physical clamp (`clamp_min_minutes`) may now be **0**, and the
  shipped `config.example.toml` default is 0. When a line genuinely empties
  out, a sub-minute transit is real data; the previous 1-minute floor silently
  discarded it. The too-short rejection message now names the *configured*
  minimum instead of a hardcoded "1 minuto", so a fork that raises the floor
  shows its own value. Forks inherit the new default via `config.example.toml`;
  an existing install that wants it must set `clamp_min_minutes = 0` in its own
  gitignored `config/config.toml` and redeploy.

### Removed
- The `default_seed_minutes` estimation setting — there is no fabricated seed
  anymore (see "sem registro" above), so the key is obsolete. An existing
  `config/config.toml` that still lists it keeps loading (the key is ignored);
  delete the line when convenient. To adopt the empty-line behaviour, also set
  `clamp_min_minutes = 0` and redeploy.

## [0.2.4] - 2026-07-12

### Changed
- Raised the single-sample validity ceiling (`clamp_max_minutes`) from 60 to
  120 minutes. Peak-rush waits were observed running past an hour and were
  being rejected as implausible, so genuine data was silently discarded and
  estimates biased low; a 2h ceiling admits them while still rejecting the
  physically impossible. This is the value clamp only — it is independent of
  `block_minutes` (the time-of-day bucketing), which is unchanged. Forks
  inherit the new default via `config.example.toml`; an existing install must
  update its own gitignored `config/config.toml` and redeploy.

## [0.2.3] - 2026-07-04

### Added
- Automatic database backups. A `backup` sidecar (installed with `docker compose
  up`, no host cron) writes a consistent snapshot of the SQLite database to
  `backups/` once a day using SQLite's online backup — the bot keeps serving
  during the snapshot — and rotates to the most recent `[backup].keep` (default
  30). The `[backup]` config section is optional, so an install written before
  this feature keeps working and still gets backups. The entrypoint now also
  fixes ownership of the bind-mounted `backups/` directory. docs/DEPLOY.md §5
  covers on-demand backups, copying snapshots off the Pi, and restore.

## [0.2.2] - 2026-07-02

### Fixed
- Docker first run on a rootful host no longer needs a manual `chown`. The
  daemon creates a missing bind-mounted `data/` as `root:root`, which the
  unprivileged bot user could not write, so the SQLite database failed to open.
  The container now starts as root and an entrypoint shim (`enfilera.entrypoint`)
  chowns the data volume to the app user and drops privileges before exec — the
  database opens on any host, whatever the operator's login UID. A tracked
  `data/.gitkeep` keeps the directory present in a fresh clone.

## [0.2.1] - 2026-07-02

### Changed
- The `/registrar` location prompt now explains that the shared location is
  used only to confirm presence at the restaurant and is discarded right
  after — never stored. Reassures privacy-wary users so we don't lose
  contributors (or field questions) over the location request.

## [0.2.0] - 2026-07-01

### Added
- Admin `/usuarios` command: distinct active (submitting) users today and over
  a rolling 30-day window, with a per-line breakdown. Counts come from the
  submissions table (one row per user holds their latest submission), so the
  figures are exact and the per-line split partitions users without double-
  counting; samples stay anonymous. A schema migration adds `line_id` to the
  submissions row.

## [0.1.0] - 2026-06-30

### Added
- Project scaffold: `uv`-managed Python package with a `src/` layout.
- Tooling: `pytest` (single-command test runner), `ruff` (lint, warnings as
  errors, cyclomatic-complexity gate), and `black` (formatter).
- CI on every push and PR: format check, lint, full test suite, and a
  dependency audit (`pip-audit`). A red build blocks merge.
- Forkable example configuration (`config/config.example.toml`); the real
  `config/config.toml` and the bot token stay out of version control.
- Time & period engine (pure, I/O-free): config parsing/validation, the
  open/closed check (operating days, periods, closures, halt) on server time
  with timezone/DST handling, timestamp → (period, block) mapping, the
  one-submission-per-period identity, and the previous-block fallback.
- Estimation core (pure, I/O-free): the sample-validity pipeline (physical
  clamp + relative outlier rejection against the historical baseline, guarded
  for MAD = 0 and tiny n), robust aggregation (median / 20% trimmed mean),
  confidence gating (previous block → historical seed → configured default),
  and "~N min" output formatting. Works in seconds; the `[estimation]` config
  is parsed and validated (minutes → seconds).
- Shared config-parsing validators reused across the schedule and estimation
  config builders.
- Persistence layer over a single SQLite file, behind thin per-entity stores
  with the connection injected: schema migrations via `PRAGMA user_version`
  (fresh fork comes up empty-clean), raw-sample write + windowed read +
  retention pruning, the one-submission-per-period record/query, closure
  declare/range/active/upcoming/revoke + past-closure pruning, and the halt
  flag. Includes the scheduled pruning job that keeps the database bounded.
- Telegram bot (user flows): structured JSON logging and the application
  bootstrap (token from env); line selection (`/fila`), the live wait estimate
  (`/agora`), the geofence-gated register-time timer (`/registrar` → location →
  `/parar`) with a confirm/resume guard against a premature stop, bug-report
  and author links (`/bug`, `/sobre`), and a per-user flood guard. The shared
  location is a presence check only and is never stored.
- Composition root and `python -m enfilera` entrypoint: a config loader
  assembles the full static config from one TOML file and wires the stores,
  services, and handlers, so the bot runs end to end.
- Admin commands (operator control from the phone), gated by the
  `[bot].admin_ids` allowlist: halt/resume the bot (`/pausar`, `/retomar`),
  declare a closure for a day, a single period, or a date range with an
  optional reason (`/fechar`), list upcoming closures (`/fechamentos`),
  revoke a specific closure (`/reabrir`), and report the live
  open/closed/halt state and why (`/status`). A non-admin gets a refusal and
  changes nothing; closure-argument parsing is pure and reports the offending
  token on bad input.
- Deploy & operations: a one-command, container-based deploy that runs the same
  anywhere Docker runs — a Raspberry Pi, a VPS, or a laptop. `bin/deploy` wraps
  `docker compose up -d --build`, and the *same* command targets a remote host
  via `DOCKER_HOST=ssh://…` or a Docker context; the container's
  `restart: unless-stopped` policy keeps the bot up across crashes and reboots
  without systemd. The SQLite database persists in a mounted `data/` volume
  (copy it to back up); the token comes from the gitignored
  `config/enfilera.env`. Adds a tag-triggered release workflow that builds the
  wheel + sdist once and publishes the version's CHANGELOG section as the
  GitHub Release body (`bin/changelog-section`), plus `docs/DEPLOY.md` (fork,
  deploy, operate, back up, release).
- Pruning entrypoint `python -m enfilera.prune`, run automatically by a `prune`
  sidecar service in `compose.yaml` that prunes once a day — the retention job
  (Feature 3) now ships with the deploy with no host cron to remember.
  Previously the job existed but nothing invoked it, so the database would have
  grown without bound. The connection sets a `busy_timeout` so the bot and the
  sidecar can share the one SQLite file without "database is locked" errors.
