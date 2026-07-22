# ICSA — Frontend Guide

This document explains the ICSA frontend: how it is built with **Streamlit**, how
authentication and routing work, what each dashboard renders, and how to add new
pages or tabs. For the big-picture design (layers, tenancy, how a chat message
flows end-to-end), read [architecture.md](architecture.md) first — this doc does
not repeat it.

The frontend is a **Streamlit monolith**. There is **no HTTP API**: the UI
imports backend service classes directly (e.g. `from
backend.services.menu_service import MenuService`) and calls them in-process. A
database session is opened per interaction with `next(get_db())` and closed in a
`finally` block. All frontend code lives under `frontend/`.

```
frontend/
├── app.py                       # entrypoint: CSS, auth guard, role routing
├── styles.css                   # injected global CSS (dark glassmorphic theme)
├── .streamlit/config.toml       # Streamlit theme + server config
├── components/
│   ├── auth_ui.py               # login / register screen
│   ├── sidebar.py               # navigation, logout, system status
│   ├── customer_dashboard.py    # Chat / Menu / My Orders
│   ├── restaurant_dashboard.py  # manager tools (7 tabs)
│   └── admin_dashboard.py       # platform analytics + management
└── utils/
    ├── session.py               # chat-history session state helpers
    └── auth_helper.py           # login/logout/JWT validation/permissions
```

---

## 1. How Streamlit works (the mental model)

A Streamlit app is a **plain Python script that re-runs top to bottom on every
user interaction**. Clicking a button, typing in a chat box, changing a
selectbox — each of these reruns `frontend/app.py` from line 1. There is no
callback/event tree kept alive between clicks; the "current UI" is simply
whatever the script drew on its most recent run.

Because locals are wiped on every rerun, persistent state lives in
**`st.session_state`** — a per-browser-session dict that survives reruns. ICSA
keeps the logged-in user, the JWT, the active page, and the chat history there.
When you need to force an immediate rerun after mutating state (e.g. after
login), call `st.rerun()`. Keep this model in mind while reading the rest of this
doc: every function below runs in full on each interaction.

---

## 2. `app.py` — the entrypoint (auth guard + routing)

`frontend/app.py` runs on every rerun and does five things in order:

1. **Path + page setup.** Adds `frontend/` and the repo root to `sys.path` so
   both `utils...` and `backend...` imports resolve, then `st.set_page_config(...)`
   (title "ICSA - Customer Support", centered layout, expanded sidebar).
2. **Loads CSS** from `frontend/styles.css` and injects it via `st.markdown(...,
   unsafe_allow_html=True)`.
3. **Initializes session state** — `init_session_state()` (chat defaults) and
   `init_auth_session_state()` (auth defaults).
4. **Auth guard.** Calls `check_auth()`. If it returns `False`, the app renders
   `render_auth_ui()` (the login/register screen) and calls `st.stop()` so nothing
   below runs. An unauthenticated visitor can never reach a dashboard.
5. **Renders the sidebar**, then routes to a dashboard based on
   `st.session_state.active_view`.

### The auth guard re-validates the JWT on every run

`check_auth()` (in `frontend/utils/auth_helper.py`) does not just check a boolean.
On each rerun, if the session is marked authenticated, it **cryptographically
re-validates the stored JWT** with `AuthService.validate_access_token(...)`. If the
token is expired or tampered with, it clears the auth state, shows a "session
expired" warning, and reruns back to the login screen. This means every
interaction is re-checked against a live token, not a stale flag.

### Role-based routing with permission checks

After the sidebar, `app.py` reads `active_view` and dispatches to the matching
dashboard, but **only after a permission check**:

| `active_view`             | Permission required   | Renders                        |
| ------------------------- | --------------------- | ------------------------------ |
| `💬 Customer Dashboard`   | `chat:read_write`     | `render_customer_dashboard()`  |
| `📊 Restaurant Dashboard` | `analytics:read_own`  | `render_restaurant_dashboard()`|
| `⚙️ Admin Dashboard`      | `admin:manage_system` | `render_admin_dashboard()`     |

Each branch calls `has_permission(...)`; if it fails (or `active_view` is
unrecognized) the app shows "Permission Denied" and stops. `has_permission()`
delegates to `backend.core.permissions.has_permission(role, permission)`, so the
UI and backend share one permission source of truth.

---

## 3. Session state & auth helpers (`frontend/utils/`)

### `session.py`

`init_session_state()` seeds chat-related keys if missing:

- `messages` — list of chat message dicts (`{role, content, ...}`), pre-seeded
  with a welcome message from the assistant.
- `selected_restaurant` — the active restaurant context (defaults to
  `"Restaurant_A"`).
- `typing_speed` — delay (seconds) used to simulate the assistant "typing"
  (default `0.02`).

`clear_chat_history()` resets `messages` to a single cleared-state greeting; it is
wired to the sidebar's **🧹 Clear Conversation** button.

### `auth_helper.py`

This module owns authentication and talks to `backend.services.auth_service.AuthService`.

Keys it manages in `st.session_state`:

| Key                   | Meaning                                                                                     |
| --------------------- | ------------------------------------------------------------------------------------------- |
| `is_authenticated`    | `bool` — is a user logged in                                                                |
| `access_token`        | the signed JWT string                                                                        |
| `user`                | dict `{id, email, role, first_name, last_name, restaurant_id}` (or `None`)                   |
| `active_view`         | the current page label (drives routing in `app.py`)                                          |
| `selected_restaurant` | the restaurant context (locked to the manager's own restaurant for the `restaurant` role)   |

Key functions:

- **`init_auth_session_state()`** — ensures `is_authenticated`, `access_token`,
  and `user` exist (defaults: `False`, `None`, `None`).
- **`login_user(email, password_raw)`** — authenticates via
  `AuthService.authenticate_user`, mints a JWT with
  `AuthService.create_access_token`, stores the token and the `user` dict, then
  calls `init_landing_view(role)` to pick the correct starting page. Returns
  `(success, message)`.
- **`register_user(...)`** — creates a new account through
  `AuthService.register_user`. Supports **restaurant onboarding**: a
  "Restaurant Manager" signup passes a `restaurant_name` that provisions a new
  tenant.
- **`logout_user()`** — clears `is_authenticated`, `access_token`, and `user`,
  then `st.rerun()` back to the login screen.
- **`check_auth()`** — the per-run JWT re-validation described above; also
  initializes `active_view` if unset and pins `selected_restaurant` to the
  manager's own `restaurant_id`.
- **`has_permission(permission)` / `has_role(role)`** — thin wrappers that
  require an authenticated user, then defer to
  `backend.core.permissions`.
- **`init_landing_view(role)`** — maps role → default `active_view`
  (`admin` → Admin Dashboard, `restaurant` → Restaurant Dashboard, otherwise
  Customer Dashboard).

### The login / register screen (`components/auth_ui.py`)

`render_auth_ui()` renders a two-tab glassmorphic screen:

- **🔑 Sign In** — an `st.form` collecting email + password; on submit calls
  `login_user(...)` and reruns on success.
- **📝 Create Account** — email, password (min 8 chars) + confirm, optional
  name, and a role selectbox ("Customer Support User" → `UserRole.CUSTOMER`,
  "Restaurant Manager" → `UserRole.RESTAURANT`). Choosing Restaurant Manager
  dynamically reveals a **Restaurant Name** field. On submit it validates and
  calls `register_user(...)`. (Admin accounts are not self-service — they are
  seeded.)

---

## 4. The sidebar (`components/sidebar.py`)

`render_sidebar()` draws the persistent left panel:

- **Branding** header.
- **🧭 Navigation** — a selectbox whose options depend on role:
  `admin` → `["⚙️ Admin Dashboard"]`, `restaurant` → `["📊 Restaurant Dashboard"]`,
  otherwise `["💬 Customer Dashboard"]`. It is bound to `st.session_state.active_view`
  via `key="active_view"`, and normalizes `active_view` if it holds a value not
  allowed for the current role. Because each role has exactly one page, the
  selectbox effectively pins the user to their allowed dashboard.
- **Role-specific controls** — admins get a **Simulator Controls** slider
  (`typing_speed`); managers get a **Context Settings** selectbox locked to their
  assigned `restaurant_id`.
- **🧹 Clear Conversation** button (`on_click=clear_chat_history`).
- **User profile card + 🚪 Log Out** button (calls `logout_user()`).
- **System status panel** — static metadata: Core Status ● Online, Version
  1.0.0, and **AI Engine: Google Gemini (RAG)**.

---

## 5. The dashboards (`components/`)

Each dashboard is one `render_*` function. They read `st.session_state.user`,
open DB sessions with `next(get_db())`, and call backend services directly.

### 5.1 Customer dashboard (`customer_dashboard.py`)

`render_customer_dashboard()` shows a welcome header, a **Select Restaurant**
selectbox (populated from `RestaurantRepository.list_active`), and three tabs:

- **💬 Chat** (`_render_chat_tab`) — the core RAG experience.
  - On first open (or when the selected restaurant changes) it loads any
    existing *active* `Conversation` for this customer+restaurant via
    `ConversationService.load_history`, otherwise starts a fresh session with
    `initialize_restaurant_conversation` (which uses the restaurant's configured
    greeting from `RestaurantService.get_ai_config` when set).
  - Message history renders with `st.chat_message`. Assistant replies that carry
    `sources` show a **📚 View Citations & Sources** expander listing each source's
    title, document type, id, and snippet.
  - User input via `st.chat_input`. The turn is persisted with
    `MessageRepository.create`, then routed through
    `process_chat_message(...)` → **`ConversationOrchestrator.orchestrate(db,
    restaurant_id, question, conversation_id=..., customer_id=...)`**. The
    orchestrator performs NLU + escalation + domain routing / RAG (see
    [architecture.md](architecture.md)). Passing `customer_id` enables
    order-status / order-modification / personalized-recommendation routing;
    `conversation_id` enables escalation persistence.
  - The answer is streamed word-by-word (throttled by `typing_speed`), then the
    assistant message is saved with its intent, sentiment, language, latency, and
    `escalated` flag. If flagged escalated, the conversation status is updated via
    `ConversationService.update_status(..., "escalated")`.
  - **Close Chat & Rate** opens a **CSAT** panel (1–5 star slider + optional
    comment) submitted through `FeedbackService.submit_feedback`.
- **🍽️ Menu** (`_render_menu_tab`) — calls `MenuService.list_products(db,
  restaurant_id)`, groups items by `category`, and renders name, description,
  price (or per-size prices), dietary tags, and a "popular" marker.
- **📦 My Orders** (`_render_orders_tab`) — calls
  `OrderService.get_customer_orders(db, customer_id)` and renders each order with
  a status badge, item summary, type, total, and placed-at time.

### 5.2 Restaurant (manager) dashboard (`restaurant_dashboard.py`)

`render_restaurant_dashboard()` is scoped to the manager's own
`restaurant_id`. It passes the session's `access_token` into services that
enforce tenant authorization. Seven tabs:

| Tab                      | Backend calls                                                                                 |
| ------------------------ | --------------------------------------------------------------------------------------------- |
| **📊 Performance Insights** | `AnalyticsService.get_restaurant_analytics` — real metric cards (tickets, CSAT, resolution rate, escalations), a sentiment trend `st.line_chart`, avg response time, and top intents. |
| **📚 Knowledge Base**       | `KnowledgeService.get_document_count` / `list_documents` / `upload_document_file` (PDF, DOCX, CSV, TXT ≤10MB, indexed into ChromaDB) / `update_document` / `delete_document`. |
| **🏪 Restaurant Profile**   | `RestaurantService.get_profile` / `update_profile` — name, contact, delivery settings, per-day business hours. |
| **🚨 Review Center & Escalation Board** | `EscalationService.get_escalations_for_restaurant` / `get_transcript` / `add_notes` / `claim_escalation` / `resolve_escalation`, with status/priority filters. |
| **🍽️ Menu**                | `MenuService.list_products` (list, incl. unavailable) and `ProductRepository.create` (add item). |
| **🤖 AI Settings**          | `RestaurantService.get_ai_config` / `update_ai_config` — toggle the AI assistant, edit the greeting, set the low-confidence escalation threshold. |
| **📦 Orders**               | `OrderRepository.list_by_restaurant` and `OrderRepository.update_status` (statuses from `backend.models.order.ORDER_STATUSES`). |

### 5.3 Admin dashboard (`admin_dashboard.py`)

`render_admin_dashboard()` presents a **Select Analysis Scope** selectbox with
five scopes:

- **Global Overview** — `AnalyticsService.get_global_analytics`: platform-wide
  metric cards, aggregated sentiment trend, avg response time, top intents.
- **Single Restaurant Detail** — pick a restaurant
  (`RestaurantRepository.list_active`), then
  `AnalyticsService.get_restaurant_analytics` for that tenant.
- **Compare Restaurants** — pick ≥2 restaurants;
  `AnalyticsService.compare_restaurant_analytics` renders a comparative table.
- **Restaurant Knowledge Base** — inspect/search any restaurant's docs via
  `KnowledgeService.list_documents` / `search_documents` / `get_document_count`.
- **Users & Restaurants** — lists all restaurants (`RestaurantRepository.list_active`)
  and all users (queried directly, excluding soft-deleted) as dataframes.

---

## 6. Recipe: add a new page or tab

**Add a tab to an existing dashboard** (most common):

1. In the dashboard component, add your label to the `st.tabs([...])` list and
   capture the new tab variable.
2. Inside `with my_tab:` render your UI. Open a DB session with
   `db = next(get_db())` and **always** close it in a `finally` block (or reuse
   the dashboard's existing `db`).
3. Call backend services/repositories directly — do not add HTTP calls. For
   manager/admin actions pass `token = st.session_state.get("access_token")` so
   tenant authorization is enforced.

**Add a whole new page** (new `active_view`):

1. Create `frontend/components/my_dashboard.py` with a `render_my_dashboard()`
   function and import it in `frontend/app.py`.
2. In `app.py`, add an `elif active_view == "🆕 My Page":` branch guarded by an
   appropriate `has_permission(...)` check, calling your render function.
3. In `frontend/components/sidebar.py`, add `"🆕 My Page"` to the `nav_options`
   for the roles that should see it (and to `init_landing_view` in
   `auth_helper.py` if it should ever be a landing page). If it needs a new
   permission, define it in `backend/core/permissions.py`.

**Persist state across reruns:** store it in `st.session_state` (remember the
script reruns top-to-bottom every interaction), and call `st.rerun()` when you
need the UI to refresh immediately after a mutation.
