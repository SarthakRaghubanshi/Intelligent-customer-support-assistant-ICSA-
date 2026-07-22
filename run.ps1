# ICSA — one-command local setup & run (Windows PowerShell).
# Usage:  ./run.ps1
$ErrorActionPreference = "Stop"

if (-not (Test-Path ".venv")) {
    Write-Host "Creating virtual environment (Python 3.13)..."
    py -3.13 -m venv .venv
}

$py = ".\.venv\Scripts\python.exe"

Write-Host "Installing dependencies..."
& $py -m pip install --upgrade pip | Out-Null
& $py -m pip install -r requirements.txt

if (-not (Test-Path ".env")) {
    Write-Host "No .env found — copying .env.example. Edit it to add your GEMINI_API_KEY." -ForegroundColor Yellow
    Copy-Item ".env.example" ".env"
}

Write-Host "Applying database migrations..."
& $py -m alembic upgrade head

Write-Host "Seeding demo data + building vector index (first run only)..."
& $py -m scripts.seed

Write-Host "Launching ICSA at http://localhost:8501 ..." -ForegroundColor Green
& $py -m streamlit run frontend/app.py
