# ICSA — PRD Completion Report

**Method:** every claim below was verified by reading the actual source code line by
line (not by file names). Evidence is cited as `file:line`. Verified against the
PRD (`Product Requirements Document - Intelligent Customer Support Assistant.pdf`).

**One-line verdict:** the core product is genuinely built and demo-ready — real
multi-tenant RAG chat, deterministic order/menu domain logic, escalation
workflow, real analytics, RBAC + bcrypt/JWT auth. Of the PRD's 10 functional
modules, **2 are fully integrated and 8 are partially integrated (none are
completely untouched)**. The gaps are concentrated in the PRD's *aspirational /
enterprise* requirements (external integrations, deep-learning models,
compliance, scale, extra channels) and in a handful of specific sub-features.

---

> **Update — four gaps subsequently closed (M1, M5, M8, M9).** See
> "Update: closed gaps" at the bottom of this report for what changed and the
> evidence. The scoreboard below reflects the current state.

## Scoreboard

| # | PRD Module | Status |
|---|---|---|
| 1 | AI Chat Assistant | 🟢 Full (multi-turn memory added) |
| 2 | Restaurant Knowledge Engine | 🟢 Full |
| 3 | Order Status Assistant | 🟢 Full |
| 4 | Menu Discovery Assistant | 🟢 Full (cuisine/category + order-based popularity) |
| 5 | Smart FAQ Engine | 🟢 Full (dedicated FAQ engine added) |
| 6 | Order Modification Assistant | 🟢 Full (real structured changes) |
| 7 | Intelligent Escalation | 🟢 Full (abuse detection + configurable rules) |
| 8 | Sentiment Analysis | 🟢 Full (real signal-based confidence) |
| 9 | Multilingual Support | 🟢 Full (Arabic + multilingual domain answers) |
| 10 | Personalized Recommendations | 🟢 Full (history + spending + cuisine + season) |

| PRD §9 AI/ML Layer | Status |
|---|---|
| L1 Data Collection | 🟢 Full |
| L2 Data Processing | 🟢 Full |
| L3 ML Models (intent/sentiment) | 🟡 Partial (rule+LLM, no trained model) |
| L4 Deep Learning (transformers) | 🔴 Not implemented |
| L5 LLM Layer | 🟢 Full (Gemini; provider deviation) |
| L6 RAG | 🟢 Full |

---

## 1. Fully integrated modules

### Module 2 — Restaurant Knowledge Engine 🟢
Per-tenant knowledge with **physical two-axis isolation**: a separate on-disk
Chroma directory `data/chroma_db/{restaurant_id}` (`retriever.py:35,95`;
`vector_store.py:121,147,169`) **and** a separate collection
`restaurant_kb_{restaurant_id}` (`vector_store.py:39,70`). Retrieval loads only
that tenant's store and returns `[]` if missing (`retriever.py:96-97`), so
Restaurant A's data can never surface for Restaurant B. All document CRUD enforces
`validate_tenant_access` (`knowledge_service.py:33,76,120,…`). Ingests
PDF/DOCX/CSV/TXT (`ingestion_service.py:58-128`, `parsers.py`).

### Module 3 — Order Status Assistant 🟢
Real `orders`/`order_items` tables (`models/order.py:23-71`). "Order Tracking"
intent routes to `OrderService.get_order_status`
(`assistant_router.py:89-98`), which reads the DB row and builds the answer from a
static status map — **no LLM, so it can't hallucinate** (`order_service.py:96-111`).
Order number parsed from free text (`order_service.py:38-43`). Scoped to both the
**customer and the restaurant** (`order_repository.py:80-105`;
ownership re-check `order_service.py:81-82`). The PRD §10 workflow (verify identity
→ retrieve → check status → respond) is present, and the seeded example
order #1254 "preparing, ~20 min" is the PRD's canonical example
(`seed.py:147-150`).

### Also fully integrated (infrastructure / cross-cutting)
- **Tenant isolation (SQL + vectors)** — `core/tenant.py:5-21`; every analytics/repo
  query filters `restaurant_id`.
- **RBAC** — `core/permissions.py:5-24` (customer/restaurant/admin → permission
  lists); enforced in services (`auth_service.py:136-158`) and the frontend router
  (`app.py:58-75`).
- **Auth** — bcrypt password hashing (`core/security.py:7-9`); JWT HS256, 60-min
  expiry, `role` claim (`auth_service.py:78-95`, `config.py:43-46`); admin
  self-registration blocked in **both** backend (`auth_service.py:31-32`) and UI
  (`auth_ui.py:87-90`); unified login + role routing (`auth_helper.py:53-68`).
- **Analytics (real aggregations, not mocked)** — see §12 below; 6 of 7 metrics are
  genuine SQL queries.
- **RAG pipeline (PRD §9 Layer 6)** — retrieve → distance-threshold gate → grounded
  prompt → Gemini → source dedupe (`rag_service.py:21-131`).

---

## 2. Partially integrated modules (with the exact gap)

### Module 1 — AI Chat Assistant 🟡
NLU + RAG + Gemini generation all work (`conversation_orchestrator.py:89-181`;
`rag_service.py:87-93`). **Gap: no true multi-turn memory.** The LLM receives only
the current message — `build_rag_prompt` assembles `system + context + current
query` with no prior-turn block (`prompt_builder.py:110-117`); prior turns are
loaded only for UI display (`customer_dashboard.py:119-131`). So "multi-turn
conversation / context awareness" is UI-only, not model-level.

### Module 4 — Menu Discovery Assistant 🟡
Dietary, budget/price, and popularity filters work
(`menu_service.py:37-68`; router detection `assistant_router.py:24-49`). **Gaps:**
(a) **cuisine-type filtering not wired** — `discover()` accepts `category` but the
router never passes it (`assistant_router.py:62-64`); (b) "**most popular today**"
is a static seed flag `is_popular`, not a time-windowed order count;
(c) previous-orders filtering lives only in the separate recommendation branch.

### Module 5 — Smart FAQ Engine 🟡
The 5 named topics (delivery charges, pickup, refund, payment, hours) are
answerable, **but there is no dedicated FAQ engine** — they're handled by the
generic RAG pipeline over ingested docs (`rag_service.py:32-93`). No FAQ intents or
curated answer templates; coverage depends entirely on what was uploaded.

### Module 6 — Order Modification Assistant 🟡
The **5-minute window and status rules are genuinely enforced**
(`order_service.py:117-134`). **Gap: the mutation is a stub.** A "successful"
modification only appends the raw sentence to `order.notes`
(`order_service.py:155-156`) — it does **not** re-price, rebuild items, or update
contact details (the `OrderItem.modifiers` field exists but is never written). It
does not parse "remove ingredients / add toppings / update contact." The success
message says *"Done — I've applied this change"* (`order_service.py:160`), which
**overstates** what actually happened.

### Module 7 — Intelligent Escalation 🟡
**4 of the 5 PRD triggers + a 6th (human-assistance keywords)** are implemented,
in priority order: refund intent, complaint intent, human-assistance keyword,
negative sentiment, low confidence (`escalation_engine.py:23-96`). Persistence and
the full staff claim/resolve/notes/transcript workflow are real and tenant-scoped
(`escalation_service.py:28-183`). **Gap: "abuse detection" trigger is not
implemented** — no profanity/abuse rule exists anywhere.

### Module 8 — Sentiment Analysis 🟡
3-class Positive/Neutral/Negative (`sentiment_classifier.py:25-141`), feeds
escalation (`escalation_engine.py:88-91`) and the analytics sentiment trend
(`analytics_service.py:116-152`). **Gap: confidence scores are hardcoded
constants**, not real model probabilities (`sentiment_classifier.py:19-23`), so the
low-confidence escalation rule is effectively never tripped by rule-classified
messages.

### Module 9 — Multilingual Support 🟡
Detects English, Hindi, Spanish, French, German, and the RAG-path prompt instructs
Gemini to reply in the detected language (`prompt_builder.py:71-75`). **Gaps:**
(a) **Arabic — a PRD-required language — is entirely absent** (zero matches for
Arabic/`ar` anywhere); (b) **domain-routed answers (order/menu/recommendation) are
hardcoded English templates** that bypass the prompt builder
(`assistant_router.py:92-113`), so only the RAG/FAQ path is multilingual.

### Module 10 — Personalized Recommendations 🟡
Uses the customer's **order history** — tallies favorite categories weighted by
quantity, biases picks, falls back to popular items for new customers
(`order_service.py:165-204`). **Gap: only 1 of the 4 PRD signals.** Cuisine
preference, spending pattern, and seasonal trends are **not implemented**.

### AI/ML Architecture (PRD §9) — Layer 3 🟡
Intent and sentiment "ML models" are **regex rules + a Gemini fallback**, not
trained classifiers (no sklearn/torch, no learned weights)
(`intent_classifier.py:30-243`, `sentiment_classifier.py:25-141`).

### User type — Restaurant Manager 🟡 / Platform Administrator 🟡
- **"Train FAQs" is not a feature** — `faq` is just one selectable `document_type`
  for uploads (`document_types.py:8`); no Q&A trainer.
- **"Review AI conversations" is escalation-only** — the transcript viewer exists
  only inside escalated tickets (`restaurant_dashboard.py:394-401`); there is no
  general conversation browser.
- **Admin** can monitor analytics/KB but has **no AI-config editing UI and no
  escalation-review panel** in the admin dashboard (those live in the restaurant
  dashboard).

### §11 Restaurant Administration — item 5 🟡
"Configure escalation rules" is **only a low-confidence threshold slider**
(`restaurant_dashboard.py:544-552`); the other 4 rules are hardcoded
(`escalation_engine.py:10-53`), not tenant-configurable.

---

## 3. Completely untouched / not implemented

None of the 10 core functional modules are completely untouched. These
PRD requirement areas have **zero implementation**:

- **PRD §9 Layer 4 — Deep Learning (transformer models):** no custom/fine-tuned
  transformers; the only transformer usage is calling the hosted Gemini API.
- **PRD §10 — Delivery Question Workflow** ("do you deliver to my area?" → capture
  address → validate delivery zone → return result): **no code** — there's no
  `Delivery Inquiry` branch in the router (`assistant_router.py:81-115`); it's
  answered purely by RAG over the delivery text docs. No address capture, no zone
  validation.
- **PRD §12 — Conversion-impact metric:** not computed anywhere; no link between
  conversations and orders/revenue.
- **PRD §14 — All 8 integrations:** Restaurant Management System, POS, Payment
  Gateway, Delivery Management, CRM, Email, SMS, Push Notifications — **none**
  implemented.
- **PRD §6 — Mobile application chat:** no mobile app. **Website chat *widget*:** no
  embeddable widget (there's an in-app chat page, not a drop-in widget).
- **PRD §13 — Encryption at rest, encryption in transit (TLS), GDPR/CCPA/PCI
  compliance:** none (plaintext SQLite + local Chroma; single Streamlit process; a
  hardcoded dev JWT-secret fallback in `config.py:39-42`).
- **Abuse-detection escalation trigger** (PRD Module 7): not implemented.
- **Arabic language** (PRD Module 9): not implemented.

---

## 4. Consolidated list — required by PRD but missing

**Conversation / AI**
1. Multi-turn conversational memory (LLM only sees the current message).
2. Abuse-detection escalation trigger.
3. Arabic language support; domain answers ignore detected language.
4. A dedicated FAQ engine (currently generic RAG).
5. Trained ML/DL models — intent/sentiment are rules+LLM; no deep-learning layer.
6. Real classifier confidence probabilities (currently hardcoded constants).

**Order / menu domain**
7. Order modification that actually changes the order (re-price / rebuild items /
   update contact) — currently only appends a note.
8. Menu discovery by cuisine type; "most popular today" (time-windowed).
9. Recommendations by cuisine preference, spending pattern, seasonal trends.
10. Structured delivery-zone validation workflow (address capture + zone check).

**Admin / analytics**
11. "Train FAQs" feature for managers.
12. General conversation/transcript review (beyond escalated tickets).
13. Full per-restaurant escalation-rule configuration (only a threshold today).
14. Admin UI for AI-config management and escalation review.
15. Conversion-impact analytics metric.

**Channels / integrations / NFR (mostly aspirational per PRD scale)**
16. Website chat widget (embeddable) and mobile app.
17. All §14 integrations: RMS, POS, payment gateway, delivery mgmt, CRM, email,
    SMS, push.
18. Encryption at rest, TLS in transit, GDPR/CCPA/PCI compliance, audit logging.
19. Scale/HA targets: 10,000+ restaurants, 1M+ conversations/month, 99.9% uptime
    (single-node SQLite/Streamlit today).
20. Formal QA/KPI measurement: intent accuracy ≥90%, FAQ resolution ≥80%, <3s
    response SLA (latency is tracked but never benchmarked/enforced).

---

## Honesty flags (things the code claims but doesn't do)
- Order modification replies *"Done — I've applied this change"* but only writes a
  note (`order_service.py:160`).
- Recommendations messaging implies rich personalization but uses only order
  history.
- "Multilingual" applies only to the RAG path, not order/menu/recommendation
  answers, and excludes Arabic.
- "Configure escalation rules" is a single threshold slider, not rule config.

---

## Update: closed gaps (M1, M5, M8, M9)

These four gaps were subsequently implemented and verified.

### M1 — Multi-turn memory → 🟢 Closed
The orchestrator now fetches the recent conversation turns and passes them to the
LLM. `conversation_orchestrator.py` builds a `history` list from
`MessageRepository.list_by_conversation` (dropping the just-persisted current
question) and passes it to `RAGService.answer_question(..., history=history)`;
`rag_service.py` forwards it to `build_rag_prompt`, which renders a
`Recent conversation:` block plus a follow-up-resolution instruction
(`prompt_builder.py`). The model can now resolve references like "what about the
large one?". (Deterministic domain answers remain single-turn by design.)

### M5 — Smart FAQ Engine → 🟢 Closed
New `backend/services/faq_service.py`: a **dedicated** engine (not generic RAG)
that parses each restaurant's curated FAQ document into Q/A pairs and returns the
**exact stored answer** on a confident keyword match (Jaccard ≥ 0.30, ≥ 2 shared
keywords) — deterministic, no LLM, no hallucination. Wired into the orchestrator
before RAG; falls back to RAG on no confident match. Verified: 22 FAQ pairs
parsed for Pizza Paradise; "how much is delivery", "gluten-free crust", "operating
hours", "cash on delivery", "refunds" all matched the correct curated answer.

### M8 — Real sentiment confidence → 🟢 Closed
`sentiment_classifier.py` no longer returns the flat `SENTIMENT_CONFIDENCE_MAP`
constants. Rule-layer confidence is now derived from the **number of matched
sentiment cues** (`_signal_confidence`): e.g. "good" → 0.74, "great, amazing,
delicious" → 0.96, one negative cue → 0.76, several → 0.97, weak neutral → ~0.63.
Confidence now varies with the input signal.

### M9 — Arabic + multilingual domain answers → 🟢 Closed
- **Arabic** added to the rule detector (Arabic script range + keywords) and the
  Gemini fallback enum (`language_detector.py`). Verified: "مرحبا، أين طلبي؟" →
  Arabic/`ar`.
- **Domain + FAQ answers now honor the detected language.** A `translate_text`
  helper (`core/gemini_client.py`) translates the deterministic order/menu/
  recommendation/FAQ answers into the customer's language; the orchestrator calls
  it for any non-English/Unknown language (graceful no-op/passthrough on
  English or API failure). Previously only the RAG path was multilingual.

All four were verified without regressions (`scripts/ui_smoke.py` still 4/4;
FAQ + sentiment + Arabic detection tested directly).

---

## Update 2: remaining in-scope gaps closed

A second pass closed every realistically-implementable gap. Enterprise-infra
items that cannot be genuinely built in a single-node Streamlit app (real
encryption-at-rest/TLS, GDPR/PCI certification, a mobile app, bespoke
deep-learning model training, and live third-party POS/payment/CRM integrations)
were **not faked**; where feasible they got honest lightweight versions
(notification hooks, an audit log). New schema: `restaurants.cuisine`,
`restaurants.delivery_zones`, `orders.contact_phone`, and an `audit_logs` table
(migration `e3f4a5b6c7d8`).

### M4 — Menu Discovery → 🟢 Full
Router now passes a detected **category/section** (`_detect_category`) into
`MenuService.discover`, and **"most popular today"** is computed from actual
recent order quantities via `MenuService.popular_today` (falls back to the
curated flag). Verified: "cheap vegan pizzas under 500" filters by
vegan+pizza+price; "most popular today" ranks by order counts.

### M6 — Order Modification → 🟢 Full
`OrderService.modify_order` now **parses and applies** real changes: cancellation
(sets status), add/remove items (written to structured `OrderItem.modifiers`),
delivery instructions (order notes), and contact-number updates
(`orders.contact_phone`). The confirmation states exactly what was applied.
Verified end-to-end through the orchestrator.

### M7 — Intelligent Escalation → 🟢 Full
Added the missing **abuse-detection** trigger (`EscalationEngine._check_abuse`).
Every rule is now **toggleable per restaurant** via `ai_config.enabled_rules`
(surfaced as checkboxes in the manager's AI Settings). Escalations now also fire
a **notification** (Email/SMS/Push integration point) and an audit entry.

### M10 — Personalized Recommendations → 🟢 Full
`OrderService.get_recommendations` now uses **all four PRD signals**: order
history, **spending pattern** (preferred price tier), **cuisine preference**
(cross-restaurant), and **seasonal trend** (current month). Verified basis:
"your order history, your spending pattern, your taste for Italian food and the
season".

### Delivery-zone workflow (§10) → 🟢 Implemented
New `DeliveryService` validates a stated distance against
`restaurants.delivery_zones` and returns zone + fee + free-over + ETA; wired as a
`Delivery Inquiry` router branch. Verified: 2 km → Zone 1 (₹49, free over ₹499);
12 km → outside the 10 km radius; no distance → defers to RAG.

### Intent confidence → 🟢 Signal-based
Intent rule-layer confidence is now derived from cue count (like sentiment), so
it varies with the input (e.g. "menu" → 0.74, a rich query → 0.90 cap).

### Admin / §11 review features → 🟢 Added
- **Review AI conversations** — a manager "Conversations" tab lists all
  conversations (not just escalations) with full transcripts
  (`ConversationService.list_for_restaurant` / `get_transcript`).
- **Train FAQs** — a manager "FAQs" tab adds Q/A pairs
  (`FaqService.add_faq`); the FAQ engine answers them immediately.
- **Configure escalation rules** — per-rule toggles in AI Settings.
- **Admin escalation review** — a read-only cross-restaurant Escalations scope.
- **Audit Log** — an admin scope over `AuditService.list_recent`.

### §14 integrations / §13 compliance → honest stubs
`NotificationService` is the Email/SMS/Push integration point (logs + audits
instead of calling a provider); `AuditService` + `audit_logs` provide an
accountability trail (logins, escalations, config changes). Real
encryption/TLS/PCI/GDPR and external POS/payment/CRM integrations remain
deployment/enterprise concerns and are intentionally out of scope.

### Still genuinely out of scope (unchanged)
§9 Layer-4 bespoke deep-learning transformers; multi-LLM provider abstraction
(Gemini-only); mobile app + embeddable widget; delivery-zone *address capture /
geocoding* (numeric-distance zone validation exists); encryption-at-rest/TLS;
GDPR/CCPA/PCI certification; 10k-restaurant / 1M-conversation scale + 99.9%
uptime; formal QA/KPI benchmarking (intent ≥90%, FAQ ≥80%, <3s SLA).

Verified: migration applies cleanly, seed populates the new fields,
`scripts/ui_smoke.py` renders 4/4 (incl. the new tabs/scopes), and every new
capability was tested directly.

---

## Update 3: final gap closure + green test suite

A closing pass shut the last realistically-implementable gaps and made the whole
`tests/` suite pass on Windows. Enterprise-tier items were **not faked** (see
"Still genuinely out of scope").

### §12 — Conversion-impact analytics → 🟢 Closed
`AnalyticsService._compute_restaurant_analytics` now computes `conversion_impact`:
the share of customers who engaged the assistant and then placed an order at the
restaurant (links `Conversation.customer_id` ↔ `Order.customer_id`, tenant-scoped).
Rolled up in `get_global_analytics` too. Verified: 1 of 2 chatting customers
ordered → 50.0%.

### Module 10 — Cuisine preference now affects ranking → 🟢 Closed
Previously `fav_cuisine` was computed but only decorated the "why" text. It now
feeds `_score` via a `cuisine_match` boost, so when the restaurant matches the
customer's favorite cuisine its standout dishes rank higher. Verified: a popular
Italian item surfaces first for an Italian-preferring customer.

### Module 6 — Modifies the *named* line item → 🟢 Fixed
`modify_order` used to write add/remove modifiers to `order.items[0]` regardless
of which item the customer named. New `_pick_target_item` matches the product in
the instruction. Verified: "add extra parmesan to the Carbonara" edits Carbonara,
leaving the (first) Margherita untouched.

### §13 — Production fails hard on insecure defaults → 🟢 Fixed
`config.py` previously only *printed a warning* when APP_ENV=production ran with
the dev JWT secret / demo admin password. It now raises `RuntimeError` and
refuses to start (escape hatch: `ALLOW_INSECURE_DEFAULTS=true`). Verified both
directions (default secret → refused; strong secret → starts).

### Knowledge base — audit logging wired → 🟢 Fixed
The `TODO` audit markers in `KnowledgeService.create/update/delete_document` are
implemented via a best-effort `_audit` helper that records the acting user.
Verified: `knowledge.create` writes an audit row with the actor's email.

### Test suite → 🟢 44/44 green on Windows
All `tests/verify_*.py` now pass (exit 0). Fixes: (a) file-based test SQLite uses
`NullPool` so Windows releases the DB handle before `os.remove` teardown (excludes
`:memory:`); (b) three frontend tests add `frontend/` to `sys.path` so
`from utils.icons import …` resolves as it does under `streamlit run`; (c) Chroma
teardown `shutil.rmtree` calls made tolerant of the Windows `.bin` lock; (d) stale
assertions refreshed to current behavior — restaurant-specific greeting wording,
citation expander label, admin self-registration now *blocked* (a security
control, asserted as such), the extended `orchestrate(...)` signature, and the
`_compute_restaurant_analytics` aggregation. Note: `run_all_tests.py` still hard-
codes a foreign macOS path; a cross-platform run is `python tests/verify_*.py`
with `PYTHONUTF8=1`.
