# ICSA — Backend & Data Layer

This document teaches the **backend** of the Intelligent Customer Support
Assistant (ICSA): how the Python code is layered, what every service and
repository does, the core utilities that hold it together, and how
authentication + authorization actually work end to end.

For the big picture (what ICSA is, how a chat message flows through the whole
system, technology choices) read the [System Architecture](architecture.md)
first — this doc goes deeper on the backend and does not repeat it. For the
schema itself, see [database.md](database.md).

> ICSA is a Streamlit **modular monolith**: there is no HTTP API between the UI
> and the backend. The Streamlit frontend imports these Python service classes
> directly and calls their static methods. "Backend" here means everything
> under `backend/` — the domain logic, not a separate server.

---

## 1. The layered design

The backend is split into four layers with a strict dependency direction. Each
layer only talks to the one directly below it:

```
Frontend (Streamlit)
      │  calls static service methods, passes a JWT string
      ▼
Services      backend/services/*.py     ← authorization + tenant isolation + business rules
      │  calls repository methods
      ▼
Repositories  backend/repositories/*.py ← the ONLY place SQLAlchemy queries are built
      │  reads/writes ORM objects
      ▼
Models        backend/models/*.py       ← SQLAlchemy 2.0 declarative tables
      │
      ▼
Database      SQLite via backend/database/database.py
```

### The load-bearing rule

> **Only repositories build queries. Services enforce authorization and tenant
> isolation.**

- **Repositories** are the *only* code that constructs `db.query(...)`
  statements. They know nothing about *who* is asking — they take a `db`
  session and primitive arguments (a `restaurant_id`, an `email`) and return
  ORM objects. They apply two cross-cutting data concerns: **tenant filtering**
  (`filter(Model.restaurant_id == restaurant_id)`) and **soft-delete**
  (`filter(Model.deleted_at.is_(None))`).
- **Services** hold the business rules and — critically — the security. Before
  a service asks a repository for anything tenant-scoped, it validates the
  caller's JWT, checks their role/permission, and verifies the target tenant is
  the caller's own (or that the caller is an admin). A service method typically
  reads: *authorize → validate inputs → delegate to repository → maybe touch a
  side system (ChromaDB, analytics)*.
- **Models** are plain SQLAlchemy declarative classes. All inherit the shared
  `Base` from `backend/database/database.py`. No query logic lives here.

Why this separation matters in an interview answer: it means authorization can
never be *accidentally* skipped by writing a raw query in the UI — the UI has no
query access at all, and every repository call funnels through a service that
gates it. It also keeps the SQL in one testable place per table.

A handful of "engine" concerns (the AI pipeline, RAG, ChromaDB vector store,
NLU classifiers) live in sibling packages — `backend/rag/`,
`backend/classifiers/`, `backend/escalation/`, `backend/analytics/` — and are
orchestrated by `ConversationOrchestrator`. Those are covered in
[ai-pipeline.md](ai-pipeline.md); this doc focuses on the service/repository/model
core.

---

## 2. The services

Every service is a class of `@staticmethod`s (no instance state — the `db`
session and `token` are passed in per call). A tenant-scoped method almost
always starts by calling `AuthService.validate_tenant_access(db, token,
restaurant_id)`, which is the single choke point for "is this caller allowed to
touch this restaurant, and is that restaurant live?".

| Service (`backend/services/…`) | Key public methods | Purpose |
| --- | --- | --- |
| **AuthService** (`auth_service.py`) | `register_user`, `authenticate_user`, `create_access_token`, `validate_access_token`, `get_current_user`, `authorize_permission`, `authorize_role`, `validate_tenant_access` | Registration, login, JWT issue/verify, and the central authorization gate used by every other service. |
| **RestaurantService** (`restaurant_service.py`) | `list_active_restaurants`, `public_onboard_restaurant`, `invite_manager`, `get_profile`, `update_profile`, `get_ai_config`, `update_ai_config` | Tenant lifecycle: public self-onboarding (restaurant + owner manager, atomically), inviting more managers, profile CRUD, and per-tenant AI settings. |
| **KnowledgeService** (`knowledge_service.py`) | `create_document`, `upload_document_file`, `get_document`, `list_documents`, `search_documents`, `update_document`, `delete_document`, `get_document_count`, `rebuild_vector_store` | Manages a restaurant's knowledge base. Validates document type, persists to the relational DB, and keeps the ChromaDB vector store in sync on every create/update/delete. |
| **DocumentIngestionService** (`ingestion_service.py`) | `validate_and_parse`, `normalize_text` | File-upload pipeline: size → extension → MIME magic-byte → parse (PDF/DOCX/CSV/TXT) → normalize → empty-content check. Pure validation/parsing; no DB or auth. |
| **ConversationOrchestrator** (`conversation_orchestrator.py`) | `orchestrate` | The Step-8 AI pipeline coordinator: runs intent/sentiment/language NLU, evaluates escalation rules (auto-creating an escalation event), routes to structured-data answers or RAG, logs analytics, and returns the response contract. |
| **assistant_router** (`assistant_router.py`) | `route` (module-level function) | Domain router. Decides whether a question should be answered from *live structured data* (orders/products) vs. the RAG knowledge base. Returns a grounded answer dict, or `None` to defer to RAG. |
| **MenuService** (`menu_service.py`) | `list_products`, `discover`, `format_for_prompt` | Menu Discovery (Module 4): structured filtering of products by dietary tag, price/budget, category, and popularity. Always tenant-scoped. |
| **OrderService** (`order_service.py`) | `get_order_status`, `get_customer_orders`, `can_modify`, `modify_order`, `get_recommendations` + `extract_order_number` | Order Status (Module 3), Order Modification (Module 6, 5-minute change window), and order-history-based Personalized Recommendations (Module 10). Every lookup is scoped to both restaurant *and* customer. |
| **EscalationService** (`escalation_service.py`) | `create_escalation`, `claim_escalation`, `resolve_escalation`, `add_notes`, `get_escalations_for_restaurant`, `get_transcript` | Human-handoff workflow. Idempotent escalation creation, a `pending → claimed → resolved` state machine, tenant/role checks, and conversation-status syncing. |
| **AnalyticsService** (`analytics_service.py`) | `get_restaurant_analytics`, `get_global_analytics`, `compare_restaurant_analytics` | Real aggregations (CSAT, resolution rate, escalation rate, avg latency, top intents, 7-day sentiment trend) over conversations/messages/feedback/escalations. Per-tenant or admin-only platform-wide. |
| **FeedbackService** (`feedback_service.py`) | `submit_feedback` | Records a 1–5 CSAT rating + comment for a conversation, enforcing owner-only + one-per-conversation, then marks the conversation `resolved`. |
| **ConversationService** (`conversation_service.py`) | `start_new_session`, `load_history`, `update_status` | Conversation lifecycle: create a session for an active tenant, load a transcript (owner-checked), and drive the `active → escalated/resolved` status state machine. |

### A few services worth understanding in depth

**AuthService** is the security kernel. Everything else calls into it. Note the
lazy imports inside its methods (`from backend.core.permissions import ...`) —
this avoids circular imports because `permissions.py` imports the `UserRole`
model. It has no instance state; a JWT string is the caller's identity.

**RestaurantService.public_onboard_restaurant** is the only place a restaurant is
born. It is a *manual transaction guard*: it creates the restaurant, then the
owner `User` with role `RESTAURANT` linked via `restaurant_id`; if the user
creation fails it rolls back and deletes the orphaned restaurant. This is the
flow `AuthService.register_user` delegates to when someone registers with role
`RESTAURANT`.

**KnowledgeService** is the clearest example of "service coordinates two stores":
each write goes to the relational DB (via `KnowledgeRepository`) *and* the
ChromaDB vector store (via `backend.rag.vector_store`). On update it deletes and
re-adds the vectors so the two never drift.

**ConversationOrchestrator.orchestrate** is fault-tolerant by design — every NLU
step (`intent`, `sentiment`, `language`) and the escalation evaluation is wrapped
in try/except with a safe fallback, so a single classifier failure never breaks
the answer. It also respects the per-tenant `ai_enabled` toggle (from
`RestaurantService.get_ai_config`) and short-circuits with an "assistant is off"
message.

---

## 3. The repositories

Repositories are the data-access layer. Each maps to roughly one table and is a
class of `@staticmethod`s taking `db: Session` first. Two conventions run through
almost all of them:

- **Tenant filtering:** tenant-owned tables filter by `restaurant_id`
  (`Model.restaurant_id == restaurant_id`). Tables that hang off a conversation
  (messages, feedback, escalations) reach the tenant by *joining through*
  `conversations.restaurant_id`.
- **Soft-delete:** tables that have a `deleted_at` column always add
  `.filter(Model.deleted_at.is_(None))` on reads, and "delete" is implemented as
  `soft_delete()` setting `deleted_at = func.now()` rather than a physical
  `DELETE`.

| Repository (`backend/repositories/…`) | Exposes | Tenant filter / soft-delete |
| --- | --- | --- |
| **UserRepository** (`user_repository.py`) | `get_by_id`, `get_by_email`, `create`, `update`, `soft_delete` | Reads filter `deleted_at IS NULL`. `create` hashes the password via `security.hash_password` and lowercases the email; `update` re-hashes a `"password"` key if present. Soft-delete sets `deleted_at`. |
| **RestaurantRepository** (`restaurant_repository.py`) | `get_by_id`, `get_by_name`, `create`, `update`, `soft_delete`, `list_active`, `get_profile`, `update_profile` | This *is* the tenant table. Every read filters `deleted_at IS NULL`; `get_by_name` is case-insensitive; `list_active` returns all non-deleted tenants. |
| **KnowledgeRepository** (`knowledge_repository.py`) | `create`, `get_by_id`, `list_by_restaurant`, `search_by_document_type`, `search_by_title`, `update`, `soft_delete`, `get_document_count` | Every read filters both `restaurant_id ==` (tenant) **and** `deleted_at IS NULL`. `list_by_restaurant` paginates (limit/offset). |
| **ConversationRepository** (`conversation_repository.py`) | `create`, `get_by_id`, `update_status`, `list_by_customer`, `list_by_restaurant` | Filters by `restaurant_id` (or `customer_id`) directly. Conversations have no `deleted_at` (they cascade-delete with the tenant). |
| **MessageRepository** (`message_repository.py`) | `create`, `list_by_conversation` | Scoped by `conversation_id`; reaches a tenant only through its conversation. Stores full NLU metadata (intent, sentiment, language, latency, sources). |
| **FeedbackRepository** (`feedback_repository.py`) | `create`, `get_by_conversation` | One row per conversation (unique). `create` re-validates the 1–5 rating. Tenant reached via the conversation. |
| **EscalationRepository** (`escalation_repository.py`) | `create`, `get_by_id`, `get_by_conversation`, `list_by_restaurant`, `list_by_status`, `claim`, `resolve`, `update_notes`, `count_open_by_restaurant`, `count_resolved_by_restaurant` | Tenant scoping is done by **joining** `Conversation` and filtering `Conversation.restaurant_id ==`. `claim`/`resolve` mutate the state machine + set `assigned_to`/`resolved_by`/timestamps. |
| **ProductRepository** (`product_repository.py`) | `create`, `get_by_id`, `list_by_restaurant`, `count_by_restaurant`, `update`, `soft_delete` | Every read filters `restaurant_id ==` **and** `deleted_at IS NULL`. `list_by_restaurant` optionally filters `is_available`. |
| **OrderRepository** (`order_repository.py`) | `create`, `get_by_id`, `get_by_number`, `list_by_customer`, `get_latest_for_customer`, `list_by_restaurant`, `update_status`, `update` | Scoped by `restaurant_id` and/or `customer_id`. `create` computes line totals + order total and inserts `OrderItem`s in one go. Orders have no `deleted_at`. |

Note the division of labor for tenant safety: the repository *can* filter by
`restaurant_id`, but it trusts whatever id it's handed. It's the **service**
that guarantees the id belongs to the caller (via `validate_tenant_access`).
`EscalationService.get_escalations_for_restaurant`, for example, passes
`user.restaurant_id` (never a user-supplied id) for managers, and only admins get
the unscoped `db.query(EscalationEvent).all()`.

---

## 4. Core utilities (`backend/core/`)

These are the small, dependency-free building blocks the services lean on.

### `config.py` — environment & secrets

`Config` is a class of class-level attributes read from environment variables
(with `.env` loaded via `python-dotenv`).

- **`APP_ENV` → which SQLite DB.** `APP_ENV` (default `"development"`) selects a
  database from a hard-coded map of **absolute** paths (so the DB is the same no
  matter which directory the app is launched from):

  | `APP_ENV` | Database file |
  | --- | --- |
  | `development` (default) | `data/saas.db` |
  | `uat` | `data/uat_saas.db` |
  | `test` | `data/test.db` |

  An explicit `DATABASE_URL` env var overrides the map entirely. An unrecognized
  `APP_ENV` (e.g. `production`) falls back to the development DB — so production
  is expected to set `DATABASE_URL` explicitly. If the URL is a local SQLite
  path, the `data/` directory is auto-created at import time.
- **JWT settings.** `JWT_SECRET_KEY` (with an insecure dev fallback baked in),
  `JWT_ALGORITHM` (default `HS256`), and `ACCESS_TOKEN_EXPIRE_MINUTES` (default
  `60`).
- **Admin seed credentials.** `ADMIN_EMAIL` (default `admin@icsa.com`) and
  `ADMIN_PASSWORD` (default `AdminPass123!`). The permanent admin account is
  *seeded* from these — never self-registered (see §5).

### `security.py` — password hashing

Two functions over **bcrypt**: `hash_password(plain)` (generates a salt with
`bcrypt.gensalt()` and returns the UTF-8 hash string) and
`verify_password(plain, hashed)` (constant-time `bcrypt.checkpw`). That's the
entire cryptographic surface for passwords — `UserRepository` calls
`hash_password` on create/password-change and `AuthService.authenticate_user`
calls `verify_password` on login.

### `permissions.py` — role → permission map

A static `ROLE_PERMISSIONS` dict defines what each role can do. Roles are
**cumulative** (admin ⊇ restaurant ⊇ customer):

| Permission | customer | restaurant | admin |
| --- | :---: | :---: | :---: |
| `chat:read_write` | ✅ | ✅ | ✅ |
| `restaurant:view_menu` | ✅ | ✅ | ✅ |
| `restaurant:write_profile` | | ✅ | ✅ |
| `analytics:read_own` | | ✅ | ✅ |
| `analytics:read_all` | | | ✅ |
| `admin:manage_system` | | | ✅ |

Helpers: `get_permissions(role)`, `has_permission(role, perm)`,
`has_role(role_a, role_b)`. All accept either a `UserRole` enum or a string and
normalize internally, so they work whether they're fed a model field or a JWT
claim.

### `tenant.py` — isolation helpers

Two functions enforce the multi-tenant boundary:

- **`verify_tenant_access(user, target_restaurant_id)`** — the isolation gate.
  Admin ⇒ allowed (override). Restaurant manager ⇒ allowed **only** if
  `user.restaurant_id == target_restaurant_id`, else raises `PermissionError`.
  Customer (or anything else) ⇒ always `PermissionError` (customers can't touch
  restaurant backend resources).
- **`verify_restaurant_active(db, restaurant_id)`** — loads the restaurant via
  `RestaurantRepository.get_by_id` (which already excludes soft-deleted rows) and
  raises `ValueError` if it's missing or `is_active` is false.

`AuthService.validate_tenant_access` composes both: *get current user → verify
tenant access → verify restaurant active*. That one call is what nearly every
tenant-scoped service method leads with.

### `gemini_client.py` — single source of Gemini config

Centralizes all Google Gemini setup so model names/API key live in exactly one
place instead of being re-read across modules. Exports:

- `GEMINI_API_KEY` — read from the environment; `genai.configure(...)` is called
  once at import time if present.
- `CHAT_MODEL` — default **`gemini-2.5-flash`** (chosen for speed and a
  generous free-tier rate; override with `GEMINI_CHAT_MODEL`).
- `EMBED_MODEL` — default **`models/gemini-embedding-2`** (override with
  `GEMINI_EMBED_MODEL`).
- `get_chat_model()` — returns a configured `GenerativeModel` for chat /
  classification calls.

### `document_types.py` — canonical knowledge categories

A single `DOCUMENT_TYPES` list (e.g. `restaurant_profile`, `menu`, `faq`,
`refund_policy`, `business_hours`, `policies`, `other`, …). Used both for UI
dropdowns and as ChromaDB chunk metadata. `KnowledgeService._validate_document_type`
rejects anything not in this list.

---

## 5. Authorization, end to end

Here is how identity and permission flow through a request, using
`RestaurantService.update_profile` as a concrete example.

**1. Login mints a stateless JWT.**
`AuthService.authenticate_user` verifies the bcrypt password and that the user is
active, then `AuthService.create_access_token(user_id, email, role)` signs a JWT
with `Config.JWT_SECRET_KEY` / `HS256`. The payload carries a **role claim**:

```python
payload = {
    "sub": user_id,
    "email": email,
    "role": role,          # ← the authorization-relevant claim
    "exp": ...,            # now + ACCESS_TOKEN_EXPIRE_MINUTES
    "iat": ...,
}
```

The token *is* the caller's identity — there is no server-side session. The
frontend holds this string and passes it into service calls.

**2. Every protected call re-validates the token.**
`AuthService.validate_access_token` decodes + verifies the signature/expiry and
returns a `TokenData(user_id, email, role)`. Expired or tampered tokens raise
`ValueError`. Two thin wrappers build on it:

- `authorize_permission(token, "analytics:read_all")` → checks
  `has_permission(role, perm)` against the `ROLE_PERMISSIONS` map.
- `authorize_role(token, "admin")` → checks `has_role(role, target)`.

**3. Tenant-scoped calls also check *which* tenant.**
`AuthService.validate_tenant_access(db, token, restaurant_id)` loads the *live*
user from the DB (`get_current_user`, which also re-checks `is_active`), then runs
`verify_tenant_access` (role + ownership) and `verify_restaurant_active`. So a
manager's valid token still can't read another restaurant's profile — the
ownership check fails with `PermissionError`.

Putting it together, `update_profile` reads:

```python
@staticmethod
def update_profile(db, token, restaurant_id, update_dict):
    AuthService.validate_tenant_access(db, token, restaurant_id)  # authz + tenant + active
    validated = RestaurantProfileUpdate(**update_dict)            # schema validation
    return RestaurantRepository.update_profile(db, restaurant_id, # delegate to repo
                                               validated.model_dump(exclude_unset=True))
```

### Admin cannot be self-registered

A deliberate security invariant: the admin role is **seeded**, never created
through the public registration path. In `AuthService.register_user`:

```python
if role == UserRole.ADMIN:
    raise PermissionError("Administrator accounts cannot be created through registration.")
```

The same method also blocks public registration from *joining an existing
restaurant* (`existing_restaurant_id is not None → PermissionError`) — that path
is reserved for `RestaurantService.invite_manager`, which requires an authorized
owner/admin token. Public self-service registration can therefore only produce a
`customer`, or a `restaurant` manager *together with a brand-new restaurant* (via
`public_onboard_restaurant`). The permanent admin is created out-of-band from the
`ADMIN_EMAIL` / `ADMIN_PASSWORD` config values.

---

## 6. How it all fits — a chat turn

1. The frontend calls `ConversationService.start_new_session(db, customer_id,
   restaurant_id)` (verifies the tenant is active) to get a conversation.
2. Each user message flows into `ConversationOrchestrator.orchestrate(...)`,
   which runs NLU, evaluates escalation, and either routes to structured data
   (`assistant_router.route` → `OrderService` / `MenuService`) or to the RAG
   knowledge pipeline.
3. If escalation rules trigger, `EscalationService.create_escalation` records an
   event (idempotently) and flips the conversation to `escalated`.
4. `MessageRepository.create` persists both turns with their NLU metadata;
   `AnalyticsService` later aggregates over these rows.
5. When the customer rates the chat, `FeedbackService.submit_feedback` stores the
   CSAT and marks the conversation `resolved`.

Every one of those steps is a service method that gates access before touching a
repository — which is the whole point of the layering.
