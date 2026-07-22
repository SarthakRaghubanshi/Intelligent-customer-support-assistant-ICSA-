# PRD → Implementation Map

This document maps every functional requirement in the **Product Requirements Document (Intelligent Customer Support Assistant)** to the code that satisfies it. It is written to be read side-by-side with the source tree: each claim cites the file(s) that back it, and the final section is honest about what is production-grade versus demo-level versus out of scope.

**Stack (as built):** Streamlit frontend, a service-layer Python backend (SQLAlchemy over **SQLite**), **ChromaDB** vector store, and **Google Gemini** for embeddings + generation. There is no separate HTTP API process — the Streamlit app calls the backend service layer directly (`frontend/components/*` → `backend/services/*`). The "FastAPI-style" description refers to the layered service/repository architecture, not a running FastAPI server.

**Request flow (all chat):**
`frontend/components/customer_dashboard.py` → `ConversationOrchestrator.orchestrate` (`backend/services/conversation_orchestrator.py`) → NLU classifiers → `EscalationEngine` → **domain router** (`assistant_router.py`) *or* **RAG** (`backend/rag/rag_service.py`) → analytics logging → persisted `Message`.

> **⚠ Current status:** several modules below were later completed/upgraded and
> the "Basic" labels in the table are historical. For the authoritative,
> up-to-date status see **`completion-report.md` → "Update 2" and "Update 3"**.
> In short: multi-turn memory, a dedicated FAQ engine, Arabic + translated domain
> answers, abuse detection + per-restaurant escalation config, four-signal
> recommendations, structured order modification, delivery-zone validation,
> **conversion-impact analytics**, audit logging, and **fail-hard production
> secret checks** are all implemented, with the full `tests/verify_*` suite green
> (44/44).

---

## Summary Table

| # | PRD Module | Status | Key files |
|---|------------|--------|-----------|
| 1 | AI Chat Assistant | **Implemented** | `services/conversation_orchestrator.py`, `rag/rag_service.py`, `gemini_service.py`, `frontend/components/customer_dashboard.py` |
| 2 | Restaurant Knowledge Engine | **Implemented** | `services/ingestion_service.py`, `services/parsers.py`, `services/knowledge_service.py`, `rag/vector_store.py` |
| 3 | Order Status Assistant | **Implemented** | `services/order_service.py` (`get_order_status`), `services/assistant_router.py` |
| 4 | Menu Discovery Assistant | **Implemented** | `services/menu_service.py` (`discover`), `services/assistant_router.py` |
| 5 | Smart FAQ Engine | **Implemented** | `rag/retriever.py`, `rag/prompt_builder.py`, `rag/rag_service.py` |
| 6 | Order Modification Assistant | **Implemented** (structured add/remove/cancel/contact + rules) | `services/order_service.py` (`can_modify`, `modify_order`, `_pick_target_item`) |
| 7 | Intelligent Escalation | **Implemented** (6 rules incl. abuse; per-restaurant toggles) | `escalation/escalation_engine.py`, `services/escalation_service.py`, `frontend/components/restaurant_dashboard.py` |
| 8 | Sentiment Analysis | **Implemented** (hybrid rules + Gemini; signal-based confidence) | `classifiers/sentiment_classifier.py` |
| 9 | Multilingual Support | **Implemented** (Arabic + translated domain answers) | `classifiers/language_detector.py`, `rag/prompt_builder.py`, `core/gemini_client.py` |
| 10 | Personalized Recommendations | **Implemented** (history + spend + cuisine + season) | `services/order_service.py` (`get_recommendations`) |
| §11 | Restaurant Administration | **Implemented** | `services/restaurant_service.py`, `frontend/components/restaurant_dashboard.py` |
| §12 | Analytics Dashboard | **Implemented** (real SQL aggregations + conversion impact) | `services/analytics_service.py` |
| §13 | Non-Functional / Security | **Partial** (isolation/RBAC/bcrypt/JWT/audit-log/fail-hard-prod yes; scale/compliance no) | `core/tenant.py`, `core/permissions.py`, `core/security.py`, `core/config.py`, `services/auth_service.py`, `services/audit_service.py` |

"Basic" means the requirement is genuinely wired end-to-end but the logic is intentionally simple for a demo; see the honest-limitations section for details.

---

## Module 1 — AI Chat Assistant

**Status: Implemented.**

Every customer message runs through `ConversationOrchestrator.orchestrate` (`backend/services/conversation_orchestrator.py`), which:
1. Checks the restaurant's `ai_enabled` toggle and short-circuits with a "staff will follow up" reply if the bot is off.
2. Runs the three NLU classifiers (intent / sentiment / language), each wrapped in a fault-tolerant fallback so a classifier crash never breaks the turn.
3. Evaluates escalation rules.
4. Routes to either the **domain router** (structured data) or **RAG** for the answer.
5. Logs an analytics event and returns a single response contract.

Multi-turn conversations are **persisted**: `Conversation` and `Message` rows (`backend/models/conversation.py`, `message.py`) store role, content, intent/sentiment/language, latency, escalation flag, and citation sources. The customer UI (`_render_chat_tab` in `customer_dashboard.py`) reloads an existing active conversation's history on restaurant switch, and writes each user + assistant message back via `MessageRepository`.

Generation uses Gemini through `RAGService` → `google.generativeai`. The chat model is centralized in `backend/core/gemini_client.py` and defaults to **`gemini-2.5-flash`** (chosen for low latency and a friendlier free-tier rate limit).

> **Honest note on "multi-turn":** history is stored and re-displayed, but prior turns are **not** fed back into the LLM prompt. `build_rag_prompt` receives only the *current* question plus retrieved chunks (`rag/prompt_builder.py`), and the domain router is likewise single-turn. So the assistant has conversation *persistence* but not conversational *memory* — a follow-up like "and what about the vegan one?" is not resolved against the previous message.

## Module 2 — Restaurant Knowledge Engine

**Status: Implemented, with strong tenant isolation.**

- **Per-tenant storage:** each restaurant's knowledge lives in its own ChromaDB collection **and** its own on-disk directory. `rag/vector_store.py` builds `collection_name=f"restaurant_kb_{restaurant_id}"` inside `data/chroma_db/<restaurant_id>/`, so there is both a logical (collection) and physical (directory) boundary between tenants. Relational metadata is the `KnowledgeDocument` table, always filtered by `restaurant_id` in `KnowledgeService`.
- **Ingestion of PDF/DOCX/CSV/TXT:** `services/parsers.py` implements `PDFParser` (pypdf), `DOCXParser` (python-docx, including table cells), `CSVParser` (DictReader), and `TXTParser`. `services/ingestion_service.py` validates in order: 10 MB size cap → extension whitelist → **magic-byte signature check** (`%PDF`, `PK\x03\x04`) → parse → normalize → non-empty. Managers upload through the Knowledge Base tab; `KnowledgeService.upload_document_file` parses, saves the row, and indexes chunks into Chroma via `add_document_to_vector_store`.
- **Chunk metadata** carries `document_id`, `source` (title), `restaurant_id`, and `document_type` (`rag/vector_store.py`), which powers citations and source dedup.
- Edit/delete re-sync the vector store (`update_document` deletes then re-adds chunks; `rebuild_vector_store` does a full `sync_restaurant_knowledge_base`).

Document categories are fixed in `backend/core/document_types.py` (13 types incl. `faq`, `refund_policy`, `menu`, `business_hours`, `policies`).

## Module 3 — Order Status Assistant

**Status: Implemented, deterministic.**

When intent is `Order Tracking`, `assistant_router.route` calls `OrderService.get_order_status` (`services/order_service.py`), which reads the **`orders` table** — never the LLM — so order facts cannot be hallucinated. It:
- Resolves the order by explicit order number (`extract_order_number` regex) or falls back to the customer's latest order.
- **Enforces ownership**: an order is only returned if `order.customer_id` matches the signed-in customer (cross-customer access returns "not found").
- Produces a human-readable summary from a `STATUS_TEXT` map plus an ETA computed from `estimated_ready_at`.

If the user is anonymous and gives no order number, the router asks them to sign in or provide a number. Every lookup is scoped by both `restaurant_id` and `customer_id`.

## Module 4 — Menu Discovery Assistant

**Status: Implemented.**

`MenuService.discover` (`services/menu_service.py`) filters the **`products` table** by dietary tag, max price (min across size prices), category, popularity, and keyword — all AND-combined and tenant-scoped. The router (`assistant_router._menu_answer`) triggers discovery when intent is `Menu Inquiry` **and** a discovery-signal regex matches (`vegan`, `under ₹X`, `popular`, `recommend`, etc.), then formats a factual listing (with prices) via `format_for_prompt`. Prices are included verbatim so the model never invents them.

There is also a passive **Menu browse tab** (`customer_dashboard._render_menu_tab`) grouping items by category, and full menu CRUD for managers (`restaurant_dashboard.py`, Menu tab).

> Note: menu discovery answers are assembled **directly from the DB** (`response_source: "Menu Engine"`); they are returned as-is and do **not** go through Gemini. If a menu query has no discovery signal, or filters match nothing, the turn falls back to the RAG pipeline instead.

## Module 5 — Smart FAQ Engine

**Status: Implemented.**

FAQ/policy questions (and anything not claimed by the domain router) go to `RAGService.answer_question` (`rag/rag_service.py`):
1. `retrieve_relevant_chunks_with_metadata` runs a similarity search against the restaurant's Chroma collection (`rag/retriever.py`).
2. A **distance threshold** gates hallucination: best L2 distance `<= 0.75` → build a grounded prompt and call Gemini (`PASS_TO_GEMINI`); otherwise return the fixed fallback *"I could not find that information in the restaurant knowledge base."* (`FALLBACK`). Empty KB also returns the fallback.
3. `build_rag_prompt` (`rag/prompt_builder.py`) instructs the model to **use ONLY the provided context** and repeats an explicit no-hallucination clause (don't invent menu items, prices, policies, hours).
4. Answers carry deduplicated **source citations** (document title, type, snippet), rendered in the chat UI under "View Citations & Sources."

## Module 6 — Order Modification Assistant

**Status: Basic (business rules fully enforced; the mutation itself is a stub).**

`OrderService.can_modify` enforces the real policy: no modification once `delivered/completed/cancelled` or `out_for_delivery/ready`, and a hard **5-minute window** from `placed_at` (`MODIFY_WINDOW_MINUTES = 5`). `modify_order` re-checks ownership and the window, and on success records the request.

**Honest scope:** a successful modification only **appends the instruction as a note** on the order (`OrderRepository.update(..., {"notes": ...})`) — it does not re-price, add/remove line items, or rebuild the cart. The code comment says as much ("a real POS integration would re-price/rebuild the cart"). So the *guardrails* are production-quality; the *fulfillment* is a demo stub.

## Module 7 — Intelligent Escalation

**Status: Implemented.**

`EscalationEngine.evaluate` (`escalation/escalation_engine.py`) applies **5 rules in priority order**: (1) Refund Inquiry, (2) Complaint, (3) explicit human-assistance keywords, (4) Negative sentiment, (5) confidence below the restaurant's threshold (default 0.60, configurable per tenant). The orchestrator calls this every turn and, when it fires and a `conversation_id` exists, auto-creates an `EscalationEvent` via `EscalationService.create_escalation` (idempotent — one event per conversation — and flips conversation status to `escalated`).

`EscalationService` (`services/escalation_service.py`) implements the full manager workflow: priority mapping, a `pending → claimed → resolved` state machine, assignee-only resolve, internal notes (immutable once resolved), tenant/role guards, and transcript retrieval. The **Review Center & Escalation Board** tab (`restaurant_dashboard.py`) renders tickets with filters, transcripts, notes, and claim/resolve controls.

## Module 8 — Sentiment Analysis

**Status: Implemented (hybrid).**

`classifiers/sentiment_classifier.py` returns `Positive / Neutral / Negative` via a two-layer design: a rule/regex layer for obvious cases and mixed-signal detection, falling back to Gemini (`gemini-2.5-flash`) for ambiguous input. Sentiment feeds **two** places: it is Rule 4 of escalation (Negative → escalate), and it is injected into the RAG prompt to shape **tone** (empathetic for Negative, warm for Positive) while the prompt explicitly forbids sentiment from overriding facts or policy. Sentiment is stored per message and drives the analytics **sentiment trend**.

## Module 9 — Multilingual Support

**Status: Basic (detection + prompt instruction).**

`classifiers/language_detector.py` detects language with a rule layer (Devanagari range + curated keyword sets for English/Hindi/Spanish/French/German, plus mixed-language handling) backed by a Gemini fallback. The detected language is then **injected into the RAG prompt** (`build_rag_prompt`): if it isn't English/unknown, the model is told *"The customer wrote in <language>. Reply in <language>…"*. So replies come back in the customer's language **for the RAG path**.

**Honest scope:** actual translation quality is delegated entirely to Gemini — there is no translation layer or per-language template. The rule layer only knows five languages (others rely on the Gemini fallback). And because domain-router answers (order/menu) are built from Python string templates, those replies are **English-only** regardless of detected language.

## Module 10 — Personalized Recommendations

**Status: Basic (frequency heuristic).**

`OrderService.get_recommendations` counts the customer's historical order **categories**, biases picks toward their top categories, then fills to the limit with `is_popular` items — falling back entirely to popular items for new customers (`basis` string reflects which path was used). The router surfaces this when a `Menu Inquiry` looks personal ("recommend", "for me", "my usual") with no explicit filters. It is a transparent heuristic, not a trained recommender or collaborative-filtering model.

---

## §11 — Restaurant Administration Features

**Status: Implemented.** All via the manager's `restaurant_dashboard.py` tabs, backed by services with tenant/role checks:

| Admin capability | Where |
|---|---|
| Enable/disable AI, greeting, escalation threshold | AI Settings tab → `RestaurantService.get_ai_config` / `update_ai_config` (stored as JSON on `Restaurant.ai_config`) |
| Upload / edit / delete FAQ & docs | Knowledge Base tab → `KnowledgeService` (+ Chroma re-sync) |
| Configure profile, hours, delivery | Restaurant Profile tab → `RestaurantService.update_profile` |
| Review conversations & handle escalations | Review Center tab → `EscalationService` |
| Menu management | Menu tab → `MenuService` / `ProductRepository` |
| Order status management | Orders tab → `OrderRepository.update_status` |
| Analytics | Performance Insights tab → `AnalyticsService` |

The `ai_enabled` toggle is genuinely honored by the pipeline: `ConversationOrchestrator` reads `get_ai_config` first and refuses to answer when disabled. The greeting configured here is used to seed new conversations (`customer_dashboard.initialize_restaurant_conversation`), and the low-confidence threshold is passed into `EscalationEngine.evaluate`.

## §12 — Analytics Dashboard

**Status: Implemented with real aggregations.**

`services/analytics_service.py` computes every metric from live tables (all joined back to `Conversation.restaurant_id`, so tenant isolation holds):

| Metric | Derivation |
|---|---|
| Total conversations / tickets | `count(Conversation)` for the restaurant |
| Escalations & escalation rate | `EscalationEvent` joined to conversations |
| Resolution rate | share of conversations **without** an escalation |
| CSAT | `avg(CustomerFeedback.rating)`, 1–5 |
| Avg response time | `avg(Message.latency_ms)` for assistant messages |
| Most-asked questions | top 5 `Message.intent` for user messages |
| Sentiment trend (7-day) | `(positive + 0.5·neutral)/total` per day |

`get_global_analytics` and `compare_restaurant_analytics` provide platform-wide and side-by-side views (admin-only, enforced by `authorize_role`). The manager dashboard renders these as stat tiles, a line chart, and a top-intents table.

> Note: there is a **second, parallel** analytics path — `backend/analytics/event_logger.py` + `session_analytics.py` — that the orchestrator also invokes. It validates a 22-field event and prints an `[EVENT_LOG]` block to stdout (useful for the `verify_*` scripts). The **dashboards do not read it**; they use the SQL aggregations above. Treat the event logger as observability/logging, not the analytics source of truth.

---

## Scope & Honest Limitations

What is real and defensible in an interview:

- **Tenant isolation (data + vectors).** Every service call filters by `restaurant_id`; `core/tenant.py` blocks cross-tenant and customer-to-backend access; each restaurant has its own Chroma collection *and* directory. There are dedicated tests: `tests/verify_tenant_isolation.py`, `verify_escalation_tenant_security.py`, `verify_conversation_security.py`.
- **RBAC.** `core/permissions.py` maps `customer / restaurant / admin` to explicit permissions; `AuthService.authorize_role` / `authorize_permission` / `validate_tenant_access` gate the services (`verify_rbac.py`).
- **Password hashing.** Real **bcrypt** with per-password salt (`core/security.py`).
- **JWT auth.** Stateless HS256 tokens with `exp`/`iat`, signed from `Config` (`services/auth_service.py`).
- **Grounded RAG.** Distance threshold + "use ONLY context" + explicit no-hallucination prompt, with a deterministic fallback string when retrieval is weak.

What is intentionally demo-level (be upfront about these):

- **No conversational memory** — prior turns are persisted but not sent to the LLM (see Module 1).
- **NLU is hybrid rule-based + Gemini**, and the rule layer is tuned for a **pizza** restaurant. Reported "confidence" values are **hard-coded calibration constants** (e.g. `INTENT_CONFIDENCE_MAP`), not model probabilities.
- **Order modification** stores a note; it doesn't mutate the cart/price (Module 6).
- **Recommendations** are a category-frequency heuristic (Module 10).
- **Multilingual** output quality is fully delegated to Gemini, and template-based domain replies stay English (Module 9).
- **Single-process SQLite + free-tier Gemini.** Fine for a demo, not for concurrency or scale.

Explicitly **aspirational / NOT implemented** (PRD §13 non-functional targets):

- **99.9% uptime**, **10,000 restaurants**, horizontal scaling — no; this is one Streamlit process over a single SQLite file (`data/saas.db`).
- **Encryption at rest** — no; SQLite and ChromaDB are stored as plain local files.
- **GDPR / PCI compliance** — no; there is no audit logging (the code even has `TODO` audit-log markers in `KnowledgeService`), no data-retention/erasure tooling, and no payment handling at all.
- **Refresh tokens / password reset / email verification / rate limiting** — not present; admin accounts are seeded, not self-registerable.

## §15 — QA / Acceptance Criteria

| Acceptance criterion | Demonstrable? |
|---|---|
| Tenant isolation 100% (no cross-tenant leakage) | **Yes** — enforced in code and covered by `verify_tenant_isolation.py` and related security tests. |
| Escalation of low-confidence / complaints / refunds / human requests | **Yes** — 5-rule engine + auto-created `EscalationEvent`; `verify_escalation*.py`. |
| Grounded answers (no hallucinated facts) | **Yes, by design** — threshold gate + context-only prompt + deterministic fallback; not adversarially benchmarked. |
| Intent accuracy ≥ 90% | **Target, not measured.** No labeled test set / accuracy report exists; the `verify_*` scripts are functional smoke checks, not a scored benchmark. |
| FAQ resolution ≥ 80% | **Target, not measured.** |
| Response time < 3s | **Plausible but not benchmarked.** The default `gemini-2.5-flash` model was deliberately chosen to keep latency low (a comment in `gemini_client.py` notes `gemini-2.5-flash` added ~8s), and `avg_response_time_ms` is tracked per message — but no formal latency benchmark has been run. |

---

*Generated from a direct reading of the source. File paths are relative to the project root (`backend/`, `frontend/`).*
