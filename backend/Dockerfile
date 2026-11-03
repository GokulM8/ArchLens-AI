# ArchLens AI backend (FastAPI + deterministic pipeline)
# Build context: ./backend  (see docker-compose.yml)
FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    ARCHLENS_ANALYSES_DIR=/app/output/analyses \
    ARCHLENS_ARTIFACTS_DIR=/app/output

# All runtime dependencies ship wheels, so no compiler is needed.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Application code only — .dockerignore keeps tests, .env and output out.
COPY app/ ./app/
COPY archlens/ ./archlens/

# Source files can arrive with host-specific modes (e.g. 0700 from FAT/exFAT
# volumes); code is root-owned and world-readable, only output/ is writable.
RUN adduser --disabled-password --gecos "" --uid 10001 appuser \
    && chmod -R a+rX,go-w /app \
    && mkdir -p /app/output/analyses \
    && chown -R appuser:appuser /app/output
USER appuser

# Documentation only: the listening port is $PORT (default 8000).
EXPOSE 8000

# Fails (non-zero) on connection errors and on the 503 /health returns when
# analysis storage is not writable. Follows $PORT like the server does.
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import os,urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:%s/health' % (os.environ.get('PORT') or '8000'), timeout=4).status == 200 else 1)"

# app.serve binds 0.0.0.0 on $PORT (Render sets it), defaulting to 8000 for
# Docker Compose; one uvicorn worker, proxy headers trusted.
CMD ["python", "-m", "app.serve"]
