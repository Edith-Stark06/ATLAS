# syntax=docker/dockerfile:1

# ---- build ------------------------------------------------------------------
# Wheels are built here and only the installed result is copied forward, so the
# runtime image carries no compiler toolchain.
FROM python:3.12-slim AS build

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /build

RUN apt-get update \
    && apt-get install --no-install-recommends -y build-essential \
    && rm -rf /var/lib/apt/lists/*

# Dependency metadata first: this layer is cached and only reinvalidated when
# pyproject changes, not on every source edit. scikit-learn and shap take
# minutes to install, so the ordering matters.
COPY pyproject.toml README.md* ./
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# `pip install .` needs the package present; a stub keeps the dependency layer
# independent of the real source.
RUN mkdir -p app && touch app/__init__.py && pip install .

COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./
RUN pip install --no-deps .

# ---- runtime ----------------------------------------------------------------
FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH"

# Non-root. A container that governs financial decisions should not be running
# as uid 0 — a process escape then starts with root on the host namespace.
RUN groupadd --system atlas && useradd --system --gid atlas --home /app atlas

WORKDIR /app

COPY --from=build /opt/venv /opt/venv
COPY --chown=atlas:atlas app ./app
COPY --chown=atlas:atlas alembic ./alembic
COPY --chown=atlas:atlas alembic.ini ./

USER atlas

EXPOSE 8000

# Uses the API's own dependency check, so the container is only "healthy" once
# Postgres is actually reachable — not merely once the process is listening.
HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=5 \
    CMD python -c "import urllib.request,sys; \
sys.exit(0 if urllib.request.urlopen('http://localhost:8000/api/v1/health', timeout=4).status == 200 else 1)"

# `python -m app` rather than a bare uvicorn command: the entrypoint pins the
# event loop factory. That is a Windows requirement rather than a Linux one,
# but keeping one launch path means dev and production cannot drift.
CMD ["python", "-m", "app"]
