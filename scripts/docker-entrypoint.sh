#!/usr/bin/env bash
# Container startup: apply DB migrations, seed demo data (idempotent), then run the app.
set -e
cd /app

echo "[entrypoint] Applying database migrations..."
alembic upgrade head

# Seeding is on by default; set SEED_ON_START=false to skip (e.g. once your
# production data exists).
if [ "${SEED_ON_START:-true}" = "true" ]; then
    echo "[entrypoint] Seeding demo data (idempotent)..."
    if [ -n "$GEMINI_API_KEY" ] && [ "$GEMINI_API_KEY" != "your_google_gemini_api_key_here" ]; then
        python -m scripts.seed || echo "[entrypoint] Seed/index step reported an issue (continuing)."
    else
        echo "[entrypoint] GEMINI_API_KEY not set — seeding data without building the vector index."
        python -m scripts.seed --skip-index || true
    fi
else
    echo "[entrypoint] SEED_ON_START=false — skipping seed."
fi

echo "[entrypoint] Starting Streamlit on 0.0.0.0:8501..."
exec streamlit run frontend/app.py \
    --server.port=8501 \
    --server.address=0.0.0.0 \
    --server.headless=true
