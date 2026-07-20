# ICSA Documentation

Welcome to the documentation for the **Intelligent Customer Support Assistant
(ICSA)** — a multi-tenant, AI-powered customer-support platform for a
multi-restaurant food-ordering system.

Read these in order if you're new:

| Doc | What it covers |
| --- | --- |
| [architecture.md](architecture.md) | **Start here.** The big picture: layers, the chat-message flow, multi-tenancy, tech stack, and design decisions. |
| [ai-pipeline.md](ai-pipeline.md) | The AI/ML pipeline in depth: NLU classifiers, escalation, the RAG stack, domain routing, and how it maps to the PRD's AI architecture. |
| [backend.md](backend.md) | The service/repository/model layers, core utilities (config, security, RBAC, tenant isolation), and how authorization works. |
| [database.md](database.md) | The full schema (ER diagram + per-table reference), relationships, and the Alembic migration chain. |
| [frontend.md](frontend.md) | The Streamlit UI: routing, auth guard, session state, and every dashboard/tab and the services it calls. |
| [deployment.md](deployment.md) | How to run it — locally (one command) and via Docker — plus seed data, demo accounts, and troubleshooting. |
| [prd-modules.md](prd-modules.md) | Maps every PRD requirement to the code that implements it, with an honest scope/limitations section. |
| [interview-guide.md](interview-guide.md) | How to explain and defend the project: pitch, talking points, Q&A, and a live-demo script. |

## Quick start

```bash
# From the project root, with a Google Gemini API key in .env:
python -m alembic upgrade head        # create the database
python -m scripts.seed                # demo data + vector index
python -m streamlit run frontend/app.py
```

Then open http://localhost:8501 and sign in as `customer@icsa.com` /
`Customer123!`. See [deployment.md](deployment.md) for the one-command scripts,
Docker, and all demo accounts.
