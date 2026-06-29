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
