# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
