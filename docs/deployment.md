# ICSA — Setup & Deployment Guide

How to run ICSA locally, seed demo data, run it in Docker, and verify it works.
For how the system is put together, see [architecture.md](architecture.md); for
the UI, see [frontend.md](frontend.md).

ICSA is a single **Streamlit** app that imports its backend services directly
(no separate API server). It uses **SQLite** for data and a **ChromaDB** vector
index for RAG — both stored under `data/`. The LLM and embeddings are provided by
**Google Gemini**.

---

## 1. Prerequisites

- **Python 3.13** (the project and its pinned dependencies are verified on 3.13).
  The `run.ps1` helper specifically invokes `py -3.13`.
- **A Google Gemini API key** — free tier works. Get one at
  <https://aistudio.google.com/app/apikey>. Without it the app runs but chat/RAG
  cannot generate answers or build the vector index.
- **Git** (to clone) and, for the container path, **Docker** with Compose.

All commands below are run from the **project root** (the folder containing
`requirements.txt`, `run.ps1`, and `frontend/`).

---

## 2. Local run — the quickest way

One command bootstraps everything: creates the `.venv`, installs dependencies,
copies `.env.example` → `.env` (if missing), applies DB migrations, seeds demo
data + builds the vector index, and launches the app.

**Windows (PowerShell):**

```powershell
./run.ps1
```

**macOS / Linux:**

```bash
./run.sh
```

Both scripts do the same sequence (`run.ps1` / `run.sh`):

1. Create `.venv` if absent (Python 3.13).
2. `pip install -r requirements.txt`.
3. Copy `.env.example` → `.env` if there is no `.env` (then **edit it to add your
   `GEMINI_API_KEY`**).
4. `python -m alembic upgrade head` — apply database migrations.
5. `python -m scripts.seed` — seed demo data and build the vector index.
6. `python -m streamlit run frontend/app.py` — launch.

> First run tip: the scripts copy `.env` but cannot know your API key. If this is
> a fresh checkout, either add your `GEMINI_API_KEY` to `.env` before running, or
> stop after the copy, edit `.env`, and re-run.

The app opens at **<http://localhost:8501>**.

### Manual step-by-step (the same thing, by hand)

```bash
# 1. Create and activate a virtual environment (Python 3.13)
python -m venv .venv
# Windows:        .\.venv\Scripts\Activate.ps1
# macOS / Linux:  source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Create your .env and add your key
cp .env.example .env        # Windows: Copy-Item .env.example .env
#   then edit .env and set GEMINI_API_KEY=...

# 4. Apply database migrations (creates the SQLite schema)
python -m alembic upgrade head

# 5. Seed demo data + build the vector index
python -m scripts.seed

# 6. Launch the app
python -m streamlit run frontend/app.py
```

Then open **<http://localhost:8501>**.

---

## 3. Environment variables (`.env`)

Copy `.env.example` to `.env` and fill it in:

| Variable             | Required?             | Purpose                                                                                                  |
| -------------------- | --------------------- | -------------------------------------------------------------------------------------------------------- |
| `GEMINI_API_KEY`     | **Yes**               | Google Gemini key for chat + embeddings. RAG and indexing don't work without it.                         |
| `JWT_SECRET_KEY`     | Yes for prod          | Secret used to sign JWT session tokens. A dev fallback is used if unset, but always set it outside local dev. |
| `APP_ENV`            | No (default `development`) | `development` \| `uat` \| `test` — selects the SQLite file: `data/saas.db`, `data/uat_saas.db`, or `data/test.db`. |
| `GEMINI_CHAT_MODEL`  | No                    | Override the chat model (example in `.env.example`: `gemini-2.5-flash`).                             |
| `GEMINI_EMBED_MODEL` | No                    | Override the embedding model.                                                                             |
| `ADMIN_EMAIL`        | No (default `admin@icsa.com`) | Email of the seeded administrator account.                                                       |
| `ADMIN_PASSWORD`     | No (default `AdminPass123!`)  | Password of the seeded administrator account.                                                    |

---

## 4. Seed data & demo accounts

`python -m scripts.seed` (`scripts/seed.py`) is **idempotent** — safe to run
repeatedly; existing rows are detected and left untouched. It creates:

- the platform **admin** account,
- **3 demo restaurants** — **Pizza Paradise**, **Burgers & Co**, **Sushi Zen** —
  each with a restaurant **manager**,
- a demo **customer**,
- structured **menus** and each restaurant's **knowledge-base** documents,
- sample **orders** and a realistic 7-day **conversation history** (messages,
  escalations, CSAT feedback) so the analytics and review dashboards have real data,

and then **builds the ChromaDB vector index** for every restaurant so RAG works
immediately.

Useful flags:

- `python -m scripts.seed --skip-index` — seed data only, skip indexing (fast; no
  Gemini embedding calls).
- `python -m scripts.seed --force-index` — rebuild the vector index even if it
  already exists.

> Indexing is skipped per-restaurant when its Chroma directory already exists, so
> re-running seed after the first time is quick.

### Demo accounts (all seeded)

| Role     | Email                                                                | Password        |
| -------- | -------------------------------------------------------------------- | --------------- |
| Admin    | `admin@icsa.com`                                                     | `AdminPass123!` |
| Customer | `customer@icsa.com`                                                  | `Customer123!`  |
| Manager  | `manager.pizza@icsa.com` / `manager.burgers@icsa.com` / `manager.sushi@icsa.com` | `Manager123!`   |

(The admin email/password reflect `ADMIN_EMAIL` / `ADMIN_PASSWORD` if you set
them in `.env`.)

---

## 5. Docker

The repo ships a single-container image (`Dockerfile`) and a Compose file
(`docker-compose.yml`).

```bash
docker compose up --build
```

Then open **<http://localhost:8501>**.

What happens:

- **`Dockerfile`** builds from `python:3.13-slim`, installs `requirements.txt`,
  copies the app, exposes port **8501**, and defines a healthcheck against
  Streamlit's `/_stcore/health`. Its entrypoint is `scripts/docker-entrypoint.sh`.
- **`scripts/docker-entrypoint.sh`** runs on container start: `alembic upgrade
  head` (migrations), then `python -m scripts.seed` (idempotent). If
  `GEMINI_API_KEY` is unset/placeholder it seeds with `--skip-index` (no
  embeddings). Finally it launches Streamlit headless on `0.0.0.0:8501`.
- **`docker-compose.yml`** reads your `.env` via `env_file`, publishes
  `8501:8501`, and mounts **`./data` → `/app/data`** as a volume so the SQLite DB
  and Chroma vector index **persist across restarts**. `restart: unless-stopped`.

So the first `up` migrates + seeds + indexes; later restarts reuse the persisted
`data/` volume and start fast.

---

## 6. Verification

Two scripts confirm the stack is healthy:

- **`python -m scripts.smoke_test`** — drives the **real AI pipeline** (NLU →
  escalation → domain routing / RAG → Gemini) against the seeded DB across
  several scenarios (FAQ/RAG, store info, delivery, order status, menu discovery,
  multilingual, escalation). Requires a seeded DB **with a built vector index**,
  and makes live Gemini calls.
- **`python -m scripts.ui_smoke`** — renders **every page headless** using
  Streamlit's `AppTest` harness for the unauthenticated state and each role,
  asserting no page raises. It does **not** send chat messages, so it makes **no
  Gemini calls** — a fast, quota-free sanity check that the UI wiring is intact.

---

## 7. Troubleshooting

- **Gemini free-tier rate limits (HTTP 429).** The free tier has low
  per-minute/day quotas. When hit, the assistant degrades gracefully rather than
  crashing — space out chat messages, or set a paid/higher-quota model via
  `GEMINI_CHAT_MODEL` in `.env`.
- **First-run indexing is slow.** `scripts.seed` embeds every restaurant's
  knowledge base into ChromaDB and can take a few minutes. Subsequent runs skip
  already-indexed restaurants (use `--force-index` to rebuild, `--skip-index` to
  skip).
- **No `GEMINI_API_KEY`.** The app and seeding still run, but chat/RAG can't
  generate answers and the vector index isn't built (in Docker, seeding falls
  back to `--skip-index`). Add the key and re-run `python -m scripts.seed`.
- **Run from the project root.** `alembic`, `scripts.seed`, and `streamlit run
  frontend/app.py` all assume the current directory is the repo root (that's
  where `alembic.ini`, `data/`, and the packages resolve). Running from a
  subfolder will fail to find modules or the database.
- **Wrong/empty database.** Check `APP_ENV` — it selects which SQLite file is
  used (`development` → `data/saas.db`, `uat` → `data/uat_saas.db`, `test` →
  `data/test.db`). Seeding and running with mismatched `APP_ENV` values will look
  at different databases.
- **Docker "cannot connect to the daemon".** Docker Desktop (the engine) must be
  running before `docker compose build/up`.

---

## 8. Production deployment

The Docker image is **verified to build and run** in a clean container
(migrations → seed → Streamlit, healthy in seconds, non-root user).

### 8.1 Run it (production compose)

`docker-compose.prod.yml` uses a Docker-managed **named volume** (not a source
bind mount), sets `APP_ENV=production`, and restarts automatically:

```bash
cp .env.example .env          # then set real secrets (below)
docker compose -f docker-compose.prod.yml up -d --build
# app on http://<host>:8501  ·  logs: docker compose -f docker-compose.prod.yml logs -f
```

The container entrypoint runs `alembic upgrade head` then seeds (idempotent) on
start. Once you have real data, set `SEED_ON_START=false` to skip seeding.

### 8.2 Secrets (required in production)

Set these as environment variables / in `.env` — the app logs a security warning
if the dev defaults are used while `APP_ENV=production`:

```bash
GEMINI_API_KEY=...            # your Gemini key
JWT_SECRET_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(48))")
ADMIN_EMAIL=you@company.com
ADMIN_PASSWORD=<a strong password>
```

### 8.3 Persistence & backups

State lives under `/app/data` (the `icsa_data` named volume): the SQLite DB and
the ChromaDB index. Back it up with `docker run --rm -v icsa_data:/data -v
"$PWD":/backup alpine tar czf /backup/icsa-data.tgz -C /data .`

### 8.4 Database at scale

SQLite is fine for a single node. For higher concurrency, point `DATABASE_URL`
at Postgres (the SQLAlchemy models are portable) and add the driver:

```bash
DATABASE_URL=postgresql+psycopg://user:pass@host:5432/icsa
# add `psycopg[binary]` to requirements.txt, then: alembic upgrade head
```

### 8.5 HTTPS / reverse proxy

Streamlit serves plain HTTP on 8501. Terminate TLS with a reverse proxy. Caddy
example (`Caddyfile`), auto-HTTPS:

```
support.yourdomain.com {
    reverse_proxy localhost:8501
}
```

(Streamlit uses WebSockets — Caddy/nginx proxy them by default; for nginx add the
`Upgrade`/`Connection` upgrade headers.)

### 8.6 Cloud options

- **Any Docker host / VPS** — clone, `.env`, `docker compose -f
  docker-compose.prod.yml up -d --build`, put Caddy/nginx in front.
- **Render / Railway / Fly.io** — deploy the `Dockerfile` directly; set the env
  vars in the dashboard; attach a persistent disk/volume at `/app/data`.
- **Streamlit Community Cloud** — no Docker; point it at `frontend/app.py`, put
  secrets in the app's *Secrets* panel, and run migrations+seed once (or rely on
  the DB being created on first run). Best for a quick demo, not heavy use.

### 8.7 Known limits (see docs/completion-report.md)

Single-container demo scale; the Gemini **free tier is rate-limited** (use a paid
key + a stronger `GEMINI_CHAT_MODEL` for load); encryption-at-rest, formal
GDPR/PCI compliance, and the PRD's 10k-restaurant / 1M-conversation / 99.9%-uptime
targets are out of scope for this build.
