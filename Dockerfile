# syntax=docker/dockerfile:1
#
# Build once, run anywhere Docker runs (Pi arm64, VPS x86, a laptop). A build
# stage resolves the locked dependencies into a venv; the runtime stage carries
# only that venv plus the source, so the final image stays small and the bot
# starts straight from the venv's interpreter — no uv at runtime.

FROM python:3.12-slim AS build
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy
WORKDIR /app
# hatchling needs the package source (for the dynamic version) and the README
# (declared as the project readme) to install the project itself, so copy them
# before syncing. --frozen pins to uv.lock; --no-dev skips test/lint tooling.
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN uv sync --frozen --no-dev


FROM python:3.12-slim
WORKDIR /app
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    ENFILERA_CONFIG=/app/config/config.toml \
    ENFILERA_DB=/app/data/enfilera.db \
    ENFILERA_BACKUP_DIR=/app/backups
COPY --from=build /app/.venv /app/.venv
COPY src ./src
# The bot needs no privileges, but the entrypoint must briefly be root to fix
# the owner of the bind-mounted ./data: a rootful Docker host creates a missing
# bind source as root:root, which the unprivileged app user (UID 1000) cannot
# write. So the image keeps root as its entry user and enfilera.entrypoint
# chowns the volume to `app` and drops to it before exec — no manual `chown` on
# any host, whatever the operator's login UID. See src/enfilera/entrypoint.py.
RUN useradd --create-home --uid 1000 app \
    && mkdir -p /app/data /app/backups \
    && chown app /app/data /app/backups
# config/ is bind-mounted at runtime (config.toml) and the token arrives via
# the compose env_file; data/ and backups/ are mounted volumes holding the
# SQLite database and its snapshots, so none is baked into the image. The
# entrypoint drops to `app` at start.
ENTRYPOINT ["python", "-m", "enfilera.entrypoint"]
CMD ["python", "-m", "enfilera"]
