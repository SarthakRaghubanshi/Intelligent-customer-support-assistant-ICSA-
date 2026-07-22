#!/usr/bin/env bash
# ICSA — one-command local setup & run (macOS / Linux).
# Usage:  ./run.sh
set -e
cd "$(dirname "$0")"

if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
fi

PY=".venv/bin/python"

echo "Installing dependencies..."
"$PY" -m pip install --upgrade pip >/dev/null
"$PY" -m pip install -r requirements.txt

if [ ! -f ".env" ]; then
    echo "No .env found — copying .env.example. Edit it to add your GEMINI_API_KEY."
    cp .env.example .env
fi

echo "Applying database migrations..."
"$PY" -m alembic upgrade head

echo "Seeding demo data + building vector index (first run only)..."
"$PY" -m scripts.seed

echo "Launching ICSA at http://localhost:8501 ..."
"$PY" -m streamlit run frontend/app.py
