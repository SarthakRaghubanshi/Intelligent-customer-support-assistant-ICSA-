# ICSA — single-container image (Streamlit monolith).
FROM python:3.13-slim

# System deps: build tools for any wheels that compile, and curl for healthcheck.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1 \
    PYTHONUTF8=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install Python deps first (better layer caching).
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copy the application.
COPY . .

# Run as a non-root user (security). Give it ownership of the app + data dir.
RUN chmod +x /app/scripts/docker-entrypoint.sh \
    && useradd --create-home --uid 10001 appuser \
    && mkdir -p /app/data \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8501
HEALTHCHECK --interval=30s --timeout=5s --start-period=45s \
    CMD curl -fsS http://localhost:8501/_stcore/health || exit 1

ENTRYPOINT ["/app/scripts/docker-entrypoint.sh"]
