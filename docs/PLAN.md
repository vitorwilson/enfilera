# Enfilera — Build Plan

> Queue-wait crowdsourcing bot for university cafeterias.
> Roadmap and task breakdown. Durable *rules* live in `the project conventions`; this file
> is the project-specific *plan*, ordered by priority. Update it as scope
> changes — a feature isn't done until this file and the code agree.

## 1. The problem (use case first)

Students at a university cafeteria (*bandejão*) want to know **how long the
queue will take before the turnstile** before they walk over. A Telegram bot
crowdsources this: users start a timer when they join a line and stop it at
the turnstile; the bot reports a single estimated wait per line
(e.g. "~12 min"). Separate estimates for the **card** line(s) and the **pix**
line.

Operating reality that shapes everything:

- **Hours:** Mon–Fri, two periods — 10:30–14:30 and 17:00–20:00. Closed
  weekends, and on operator-declared closures (feriados, *pontos
  facultativos*, or ad-hoc closures — whole-day or a single period).
- **Scale:** ~8,000 *potential* users (student body); realistically a few
  hundred active/day, clustered at lunch. This is small — I/O-bound, not
  CPU-bound. A Raspberry Pi is comfortably sufficient.
- **Lines are installation-specific.** Each cafeteria has its own set of
  queues and periods. The bot must be **forkable**: edit one config, deploy,
  done.

## 2. Core domain decisions (locked)

These are settled and drive the data model and algorithm. Rationale for the
estimator lives in the research artifact from the design session; the
operational summary:

1. **Estimate = robust average of recent *personal transit times*** (join →
   turnstile) per line. It is a trailing average and lags surges; that is
   acceptable because cafeteria queues are strongly cyclical, so the
   time-of-day pattern predicts a new arrival's wait better than a live
   reading would.
2. **Time blocks:** 1-hour buckets within each operating period
   (e.g. 11:00–12:00). Each (line, block) is estimated independently and
   updated live as samples arrive.
3. **Rolling baseline, keyed by (queue, weekday, block).** Retain **raw
   samples for a configurable window (default 1 month)**; recompute the
   baseline, spread, and rejection band from them. A pruning job drops
   samples older than the window. Tuesdays-at-noon and Fridays-at-noon are
   distinct buckets.
4. **Sample validity pipeline (in order):**
   - Discard anything **< 1 minute** (given).
   - **Physical clamp** to a plausible transit band (lower bound 1 min, upper
     bound a configurable hard ceiling, e.g. ~60 min — a real lunch rush can
     take ~30 min, so the ceiling must sit well above that). The ceiling is
     the single highest-leverage poison defense after the geofence.
   - **Relative outlier rejection** against the **historical baseline** for
     that (queue, weekday, block), widened by a margin (e.g. ±k·MAD). The
     reference is the *stable historical* expectation, **never today's
     near-empty live samples** — otherwise the first (possibly poisoned)
     value of the day defines its own plausibility. Once today's block has
     ≥ N_MIN honest samples, the live spread may blend in.
5. **Robust aggregate:** median for very small n (3–5), 20% trimmed mean for
   larger n. Never the raw mean (one liar ruins it).
6. **Confidence gating:** below N_MIN (≈3) samples in today's block, show the
   **previous block's value**, falling back to the **historical baseline
   seed** for that (queue, weekday, block) if no previous block exists today.
7. **Default seed:** every (line, block) defaults to a configurable value
   (**1 min** by default) before any data exists. This is also the
   fresh-fork bootstrap: a brand-new install shows 1 min everywhere until
   real samples arrive.

## 3. Anti-abuse decisions (locked)

The threat model after geofencing + rate limiting is a *minority* of
physically-present users entering plausible-but-fake times. Robust
aggregation handles a minority; nothing handles a malicious majority in a
thin block — that is what confidence gating and the geofence exist to
prevent.

- **One submission per user per period** (10:30–14:30 and 17:00–20:00),
  enforced with **server-obtained time** so a user changing their device
  clock cannot game it. If a user already submitted this period, the
  submit/stop action is disabled until the next period.
- **Geofence:** the timer can only be *started* when the user is within a
  configurable radius (default 50 m) of the configured restaurant location.
  Geolocation is requested each time the timer is used and **never stored** —
  used only as a presence check.
- **Rate / flood protection** at the bot layer so a single user spamming
  button presses or commands cannot exhaust resources.

## 4. Configuration & operations decisions (locked)

Two layers, deliberately separated:

- **Static config file** (one file a forker edits once): queues/lines,
  operating periods, block size, geofence center + radius, retention window,
  per-(line,block) default seed, validity band parameters, admin allowlist
  (Telegram user IDs), bot token reference. Token itself comes from the
  environment / secrets, **not** committed.
- **Dynamic operational state in the database** (survives restart, changed
  from the operator's phone via admin commands): **halt/resume** the bot
  indefinitely, and **closures** (see below). **All closures are dynamic** —
  there is no config-file holiday list. One mechanism for every kind of
  closure keeps the fork story simple and avoids a static list going stale.

### Closure model

Closures cover everything: feriados, *pontos facultativos*, and ad-hoc
"not opening today for whatever reason." They differ only in scope and
timing, so a single record type captures them all:

- A **closure record** = `date` + optional `period` (null = whole day; else
  lunch or dinner) + optional `reason` label.
- **Granularity:** whole day, or a single period (e.g. lunch runs, dinner
  cancelled).
- **Reach:** today, a specific future date, or a date *range*. A range is
  **expanded and stored as one record per day** (not a range object) — this
  keeps the "is it open right now?" lookup trivial and lets a single day be
  revoked out of a range.
- **Revoke matters as much as create.** A *ponto facultativo* gets cancelled;
  a closed period gets reopened. The admin surface must support **declare**,
  **list upcoming**, and **remove a specific** closure, so a wrong or stale
  closure can't silently keep the bot dark.

When closed (weekend outside operating days, an active closure record, or a
halt), the bot shows a simple "restaurant is closed" message and accepts no
timers. The time engine's "open right now?" check consults operating
days/periods, active closure records, and the halt flag.

## 5. Build order

Backend (pure logic) → persistence/server → Telegram bot → deploy. Per
`the project conventions`, these are **not sequential walls**: the estimator and
time/period logic are pure, dependency-free functions where the real risk
lives, so they are built **test-first in isolation** before any Telegram or
network code. The bot and deploy layers are comparatively mechanical once the
core is proven.

---

## Feature 0 — Project scaffold & CI  *(priority: first)*

Foundation so every later commit is independently testable and deployable.

- [x] `git init`; Python project layout (`src/`, `tests/`, `config/`,
      `docs/`). Follow framework convention; small focused modules. (`bin/`
      lands with the Feature 6 deploy entrypoint.)
- [x] Dependency management + lockfile; pin `python-telegram-bot`.
- [x] Single-command test runner (`pytest`); recorded in the project
      conventions (replaces the `<project-specific>` placeholder).
- [x] Formatter = `black`; linter (`ruff`) warnings-as-errors.
- [x] CI on every push/PR: `black --check`, `ruff`, full test suite,
      dependency audit (`pip-audit`). Red build blocks merge.
- [x] `CHANGELOG.md` (Keep a Changelog); `README.md` opening with the
      problem + one-command quickstart (stack details go in `docs/`).
- [x] `config/config.example.*` with fake values committed; real config and
      any `.env` gitignored.

## Feature 1 — Time & period engine  *(priority: high — pure logic)*

The calendar brain. No I/O, fully unit-tested. **Always uses
server-obtained time.**

- [x] Parse operating periods and block size from config.
- [x] "Is the cafeteria open right now?" — consults operating days/periods,
      active **closure records** (whole-day or single-period), and the halt
      flag.
- [x] Map a timestamp → its (period, block) or "closed".
- [x] "Current period" identity for the one-submission-per-period rule.
- [x] "Previous block today" lookup for the confidence-gating fallback.
- [x] Edge cases: exact boundaries (10:30:00, 14:30:00), between-period gaps,
      a closure covering only one of the day's two periods, weekend, daylight
      handling for the configured timezone.

## Feature 2 — Estimation core  *(priority: high — pure logic, highest risk)*

The statistical heart. No I/O; takes samples + baseline, returns a number.
This is where most test lines live.

- [x] Validity pipeline: `< 1 min` discard → physical clamp → relative
      outlier rejection vs **historical baseline** (±k·MAD), with the
      documented guard against anchoring on today's empty live data.
- [x] Robust aggregate: median (small n) / 20% trimmed mean (larger n);
      MAD-based rejection guarded for MAD = 0 and tiny n.
- [x] Confidence gating: N_MIN threshold → previous-block → historical seed →
      configured default (1 min).
- [x] Baseline computation from the rolling raw samples for
      (queue, weekday, block).
- [x] Output formatting to a single rounded number ("~N min").
- [x] Adversarial tests: minority poison (high and low), all-identical
      values, empty/sparse blocks, clamp boundaries, first-sample-of-day.

## Feature 3 — Persistence layer  *(priority: high)*

SQLite (a single file — perfect for one Pi, trivial to fork/backup). Wrapped
behind a thin project-owned interface; dependencies injected.

- [x] Schema: raw samples (queue, weekday, block, value, server-timestamp);
      per-user last-submission-per-period; **closure records**
      (`date`, nullable `period`, nullable `reason`); halt flag. Named
      fake/in-memory DB for tests.
- [x] Write a validated sample; read samples for a (queue, weekday, block)
      window.
- [x] Record & query "user already submitted this period".
- [x] Closures: insert (a range inserts one row per day), **query active for
      a given date/period**, list upcoming, **delete a specific** one.
      Read/write the halt flag.
- [x] **Pruning job:** delete samples older than the retention window, and
      drop closure records whose date has passed.
- [x] Migrations / first-run schema creation so a fork comes up empty-clean.

## Feature 4 — Telegram bot: user flows  *(priority: medium)*

The plumbing that connects users to Features 1–3. Thin handlers; logic stays
in the core.

- [x] Bot bootstrap, token from env, structured JSON logging.
- [x] **Line selection** before use (card-bandejão / bandejinho / pix / …
      per config); changeable anytime; persisted per user.
- [x] **"How's the line today?"** → show current estimate(s) per the user's
      line, or the closed message when shut.
- [x] **"Register time"** timer: start (geofence-checked) → stop at turnstile,
      with confirm/resume; submit only if ≥ 1 min, within geofence, and not
      already submitted this period; otherwise the action is rejected with a
      clear reason. Confirm/resume guards a *premature* stop: a plausible-but-
      early value (10 min when it was 20) passes the clamp, so on /parar the
      bot shows the elapsed and lets the user resume the original timer instead
      of submitting the wrong number.
- [x] **Geofence check** on start: request live location, compare to config
      center/radius, **discard the location immediately** after the check.
- [x] **"Found a bug?"** → open/link a GitHub issue.
- [x] Author/credit info linking the operator's GitHub profile.
- [x] Per-user flood protection.

## Feature 5 — Admin commands  *(priority: medium)*

Operator control from the phone; authorization via the config allowlist.
Mutates dynamic state in the DB (Feature 3).

- [x] Authorization guard (allowlisted Telegram IDs only).
- [x] **Halt / resume** the bot indefinitely.
- [x] **Declare a closure** — for today, a future date, or a date range;
      whole day **or** a single period (lunch / dinner); optional reason.
- [x] **List upcoming closures.**
- [x] **Remove a specific closure** (revoke a *ponto facultativo*, reopen a
      closed period) — revoke is first-class, not an afterthought.
- [x] **Status** command: current open/closed/halt state and why.

## Feature 6 — Deploy & operations  *(priority: last)*

Make running it (and re-running elsewhere) a one-liner, on any host with Docker.

- [x] `bin/deploy` — the single entrypoint: `docker compose up -d --build`,
      runnable on the local host or aimed at a remote one with the *same*
      command via `DOCKER_HOST=ssh://…` / a Docker context.
- [x] **Container supervision** (`restart: unless-stopped`) for auto-restart
      across crashes and reboots, unattended — no systemd to configure. Runs the
      same on a Pi, a VPS, or a laptop, so forkability holds. (Replaces the
      original systemd-unit plan; uptime still matters more than horsepower.)
- [x] Backup/restore note for the SQLite file (the mounted `data/` volume).
- [x] `docs/DEPLOY.md` deploy + fork guide: how another student points it at
      their cafeteria (config, geofence, lines, periods) and ships their own bot.
- [x] Release flow: tag `vX.Y.Z` → CI builds the wheel/sdist and publishes;
      changelog section becomes the release body.

---

## Open / deferred (not v0.1)

- Per-user reputation weighting — conflicts with simplicity; revisit only if
  in-the-wild poisoning by a *majority* appears (the geofence/rate-limit are
  the real fix there, not a cleverer estimator).
- Multi-day blended seeds beyond the rolling baseline.
- Confidence shown to the user (we ship a single number by decision).
- Queueing-theory modeling — rejected: transit time is measured directly.
