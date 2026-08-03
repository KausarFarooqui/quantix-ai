# syntax=docker/dockerfile:1.7

# ---- Builder: resolve dependencies into a portable virtualenv ----
FROM python:3.13-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.5.11 /uv /uvx /bin/

WORKDIR /build
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

# Two-pass install: the first pass (editable, before `src` exists) just
# resolves and caches third-party dependencies from pyproject.toml alone,
# so that layer survives source-only changes. The second pass — after
# `COPY src` — reinstalls the local package for real (`--no-deps`, deps are
# already in place), replacing the editable install with an actual
# self-contained copy in site-packages.
#
# The editable install from pass one must NOT be what ships: `pip/uv
# install -e .` doesn't copy files, it points Python at this build
# directory's absolute path (`/build/src`). The runtime stage below only
# copies `/opt/venv`, not `/build` — so an editable install here becomes a
# dangling reference once `/build` no longer exists, and anything that
# imports `quantix_api` at runtime (alembic, uvicorn) fails with
# `ModuleNotFoundError: No module named 'quantix_api'`.
COPY pyproject.toml README.md ./
RUN uv venv /opt/venv --python 3.13 && \
    . /opt/venv/bin/activate && \
    uv pip install --no-cache -e ".[dev]" || uv pip install --no-cache -e .

COPY src ./src
RUN . /opt/venv/bin/activate && uv pip install --no-cache --no-deps .

# ---- Runtime: minimal image, no build toolchain ----
FROM python:3.13-slim AS runtime

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/* && \
    useradd --create-home --uid 1000 quantix

COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app
COPY --chown=quantix:quantix src ./src
COPY --chown=quantix:quantix alembic ./alembic
COPY --chown=quantix:quantix alembic.ini ./

USER quantix
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -fsS "http://localhost:${PORT:-8000}/api/v1/health/live" || exit 1

# Runs migrations on every container start rather than relying on a
# platform-specific pre-deploy hook (e.g. Render's `preDeployCommand`,
# which is paid-plan-only — see docs/DEPLOY.md). `alembic upgrade head` is
# a no-op once the database is already current, so this is safe on every
# restart, not just the first. `exec` hands off PID 1 to uvicorn so it
# receives SIGTERM directly for a clean shutdown.
#
# Binds to $PORT rather than a hardcoded 8000: hosting platforms that run
# arbitrary Dockerfiles (Render, Railway, Fly.io, Cloud Run) inject their
# own PORT and expect the container to listen on it — a hardcoded port
# works in docker-compose (nothing sets PORT there, so it falls back to
# 8000) but silently breaks on those platforms otherwise.
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn quantix_api.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 4"]
