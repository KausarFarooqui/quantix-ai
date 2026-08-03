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

COPY pyproject.toml ./
RUN uv venv /opt/venv --python 3.13 && \
    . /opt/venv/bin/activate && \
    uv pip install --no-cache -e ".[dev]" || uv pip install --no-cache .

COPY src ./src
RUN . /opt/venv/bin/activate && uv pip install --no-cache -e .

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
    CMD curl -fsS http://localhost:8000/api/v1/health/live || exit 1

CMD ["uvicorn", "quantix_api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
