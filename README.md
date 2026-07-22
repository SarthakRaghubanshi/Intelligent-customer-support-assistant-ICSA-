# Intelligent Customer Support Assistant (ICSA)

[![Python](https://img.shields.io/badge/Python-3.13-blue.svg)](#)
[![Streamlit](https://img.shields.io/badge/UI-Streamlit-red.svg)](#)
[![LLM](https://img.shields.io/badge/LLM-Google%20Gemini-4285F4.svg)](#)
[![RAG](https://img.shields.io/badge/RAG-LangChain%20%2B%20ChromaDB-green.svg)](#)
[![Multi-Tenant](https://img.shields.io/badge/Multi--Tenancy-Strict%20Isolation-orange.svg)](#)

ICSA is a **multi-tenant, AI-powered customer-support assistant** for a
multi-restaurant food-ordering platform. Each restaurant gets a chatbot that
answers customer questions grounded in **that restaurant's own** menu, policies,
delivery rules, and FAQs — plus live order status — while managers get a portal
to manage knowledge, menus, escalations, and analytics.

It combines a lightweight **NLU layer** (intent, sentiment, language), a
**Retrieval-Augmented Generation** pipeline (LangChain + ChromaDB + Google
Gemini) that keeps answers grounded and hallucination-free, and **deterministic
domain logic** for facts that must be exact (order status, prices, menu
filters). Unhappy or complex conversations **escalate to human staff**
automatically.

---

## ✨ Features

- **AI chat assistant** — multi-turn, context-aware answers (recent turns are fed
  into the model) grounded in each restaurant's knowledge base, with **source
  citations**.
- **Strict multi-tenancy** — relational data filtered by `restaurant_id`;
  vectors isolated in a per-restaurant ChromaDB collection. One restaurant can
  never see another's data.
- **Knowledge ingestion** — upload **PDF / DOCX / CSV / TXT**; documents are
  chunked, embedded, and indexed per tenant.
- **Order status & modification** — answered deterministically from the orders
  database; modifications (add/remove items, cancel, contact) apply real
  structured changes within a 5-minute window, never hallucinated.
- **Menu discovery & personalized recommendations** — structured filtering by
  dietary preference, cuisine, budget, and popularity; recommendations from order
  history, spending pattern, cuisine preference, and season.
- **Sentiment analysis & intelligent escalation** — six escalation rules
  (including abuse detection), **toggleable per restaurant**, feeding a manager
  Review Center with a claim/resolve workflow.
- **Multilingual** — replies in the customer's detected language (English, Hindi,
  Arabic, Spanish, …); deterministic order/menu answers are translated too.
- **Real analytics** — conversations, CSAT, resolution & escalation rates,
  average response time, top intents, a 7-day sentiment trend, and **conversion
  impact** (actual DB aggregations, not mocked).
- **Role-based access & security** — customer, restaurant manager, and platform
  admin, with bcrypt password hashing, JWT sessions, an append-only audit log,
  and a production guard that refuses to boot with default secrets.

---

## 🚀 Quick start

**Prerequisites:** Python 3.13 and a free [Google Gemini API key](https://aistudio.google.com/app/apikey).

### One command

```powershell
# Windows (PowerShell)
./run.ps1
```
```bash
# macOS / Linux
./run.sh
```

These create a virtual environment, install dependencies, copy `.env.example` →
`.env` (add your `GEMINI_API_KEY`), run migrations, seed demo data, and launch
the app at **http://localhost:8501**.

### Manual steps

```bash
python -m venv .venv && . .venv/Scripts/activate      # (Windows) or: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env                                   # then add your GEMINI_API_KEY
python -m alembic upgrade head                         # create the database
python -m scripts.seed                                 # demo data + vector index
python -m streamlit run frontend/app.py
```

### Docker

```bash
docker compose up --build                               # local  → http://localhost:8501
docker compose -f docker-compose.prod.yml up -d --build # production (named volume, restart policy)
```

The image is verified to build and run in a clean container (migrations → seed →
Streamlit, non-root user, healthcheck). For production, supply real secrets via
environment variables (`JWT_SECRET_KEY`, `ADMIN_PASSWORD`, `GEMINI_API_KEY`),
front the app with a TLS-terminating reverse proxy, and point `DATABASE_URL` at
Postgres for scale.

---

## 👤 Demo accounts

| Role | Email | Password |
| --- | --- | --- |
| Admin | `admin@icsa.com` | `AdminPass123!` |
| Customer | `customer@icsa.com` | `Customer123!` |
| Manager (Pizza Paradise) | `manager.pizza@icsa.com` | `Manager123!` |
| Manager (Burgers & Co) | `manager.burgers@icsa.com` | `Manager123!` |
| Manager (Sushi Zen) | `manager.sushi@icsa.com` | `Manager123!` |

Try, as the customer chatting with **Pizza Paradise**: *"Do you offer gluten-free
crust?"*, *"Where is my order #1254?"*, *"Suggest vegan options under 500"*,
*"This is terrible, I want a refund!"*.

---

## 🏗️ Tech stack

| Layer | Technology |
| --- | --- |
| UI | Streamlit |
| Language | Python 3.13 |
| LLM / Embeddings | Google Gemini (`gemini-2.5-flash` + `gemini-embedding-2`) |
| RAG | LangChain + ChromaDB |
| Database | SQLite + SQLAlchemy 2.0 |
| Migrations | Alembic |
| Auth | bcrypt + PyJWT |
| Parsers | pypdf + python-docx |

---

## 📁 Project structure

```
backend/     classifiers, core (config/security/RBAC/tenant/gemini), database +
             migrations, models, rag, repositories, services
frontend/    app.py (router + auth guard), components (dashboards), utils
scripts/     seed.py (demo data + index), smoke_test.py, ui_smoke.py
data/        SQLite DB, per-restaurant knowledge text, Chroma index
tests/       verify_*.py functional checks (run with PYTHONUTF8=1)
```

The design is a layered modular monolith: the Streamlit UI calls Python
**services** (which never import Streamlit), services use **repositories** for
data access, and the AI pipeline (NLU classifiers + RAG) is orchestrated by
`ConversationOrchestrator`. Alembic owns the schema.

---

## ✅ Verification

```bash
python -m scripts.smoke_test    # drives the AI pipeline (RAG, domain routing, escalation)
python -m scripts.ui_smoke      # renders every page headless and checks for errors
```

---

## ⚠️ Scope & honest limitations

This is a **solid, demonstrable single-node build**, not a production system.
The PRD's aspirational targets — 99.9% uptime, 10,000+ restaurants, encryption
at rest, GDPR/PCI compliance, real payment/POS integrations — are **out of
scope** here. The Google Gemini **free tier is rate-limited** (a few requests
per minute), so the assistant degrades gracefully to a fallback message under
load; set a paid key / stronger `GEMINI_CHAT_MODEL` for heavier use. The NLU is a
rules-plus-LLM hybrid (not a trained/deep-learning model), and the acceptance
KPIs (intent accuracy ≥90%, <3s response) are tracked but not formally
benchmarked.

---

## 📄 License

MIT.
