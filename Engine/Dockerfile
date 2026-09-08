# tria_engine/Dockerfile
#
# Production image for the TriaNXT CTMS FastAPI backend. Installs the
# production requirements, copies the application, and serves it through
# Gunicorn + Uvicorn workers using gunicorn_config.py (port 8000 by default,
# matching tria_engine/core/config.py's GUNICORN_BIND).

FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# System deps required by the compiled wheels (psycopg2-binary ships its own
# libpq; only the lightweight runtime bits are needed).
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies first for layer caching.
COPY requirements/prod.txt requirements/base.txt requirements/
RUN pip install --no-cache-dir -r requirements/prod.txt

# Application code (backend only — see .dockerignore).
COPY tria_engine/ tria_engine/
COPY gunicorn_config.py alembic.ini ./
COPY alembic/ alembic/

# Healthcheck against the app's own /api/health/ surface.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://localhost:8000/api/health/ || exit 1

EXPOSE 8000

# Migration entrypoint stays explicit — run `docker compose run --rm backend
# alembic upgrade head` before scaling workers (see docker-compose.yml).
CMD ["gunicorn", "tria_engine.main:app", "-c", "gunicorn_config.py"]