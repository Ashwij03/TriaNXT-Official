# tria_engine/gunicorn_config.py
#
# Production ASGI server config — run with:
#   gunicorn tria_engine.main:app -c gunicorn_config.py
#
# Worker class is Uvicorn's ASGI worker (the app is a FastAPI ASGI app).
# bind/workers/timeout read the same env vars tria_engine/core/config.py
# exposes (GUNICORN_BIND / GUNICORN_WORKERS / GUNICORN_TIMEOUT), defaulting
# to the values the Settings class already uses — so container env vars are
# the single knob for deployment tuning.

import multiprocessing
import os


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, "") or default)
    except (TypeError, ValueError):
        return default


def _env_str(name: str, default: str) -> str:
    return os.environ.get(name) or default


bind = _env_str("GUNICORN_BIND", "0.0.0.0:8000")

# One worker per CPU is a sensible starting point; overridable via
# GUNICORN_WORKERS (the same setting tria_engine/core/config.py reads).
workers = _env_int("GUNICORN_WORKERS", max(multiprocessing.cpu_count(), 2))

worker_class = "uvicorn.workers.UvicornWorker"
timeout = _env_int("GUNICORN_TIMEOUT", 120)
graceful_timeout = 30
keepalive = 5

# Access/error logs go to stdout/stderr (container-log friendly); the app's
# own logging_config.py already routes application logs the same way.
accesslog = "-"
errorlog = "-"
loglevel = os.environ.get("LOG_LEVEL", "info").lower()

# Reload must never be enabled in production containers.
reload = False

# Preload the app once per worker class copy (matches a single-entrypoint
# ASGI app; keeps memory flat across workers).
preload_app = True