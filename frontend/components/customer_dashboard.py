import streamlit as st
import time
from datetime import datetime
from utils.icons import icon, chip
from backend.database.database import get_db
from backend.repositories.restaurant_repository import RestaurantRepository
from backend.repositories.message_repository import MessageRepository
from backend.services.conversation_service import ConversationService
from backend.services.feedback_service import FeedbackService
from backend.services.menu_service import MenuService
from backend.services.order_service import OrderService

_STATUS_BADGE = {
    "placed": ("#F59E0B", "Placed"),
    "confirmed": ("#3B82F6", "Confirmed"),
    "preparing": ("#8B5CF6", "Preparing"),
    "ready": ("#10B981", "Ready"),
    "out_for_delivery": ("#06B6D4", "Out for delivery"),
    "delivered": ("#10B981", "Delivered"),
    "completed": ("#10B981", "Completed"),
    "cancelled": ("#EF4444", "Cancelled"),
}


def initialize_restaurant_conversation(restaurant_id: str, restaurant_name: str, customer_id: str = None, db=None) -> None:
    """
    Resets conversation history, sets restaurant-specific greeting with UTC timestamp,
    and updates active and current restaurant session state trackers.
    """
    st.session_state.selected_restaurant = restaurant_id
    st.session_state.current_chat_restaurant = restaurant_id

    greeting_text = f"Hello! I am your Intelligent Customer Support Assistant for {restaurant_name}. How can I help you today?"
    # Use the restaurant's configured greeting when one has been set.
    try:
        from backend.services.restaurant_service import RestaurantService
        _gdb = next(get_db())
        try:
            _cfg = RestaurantService.get_ai_config(_gdb, restaurant_id)
            if _cfg.get("greeting"):
                greeting_text = _cfg["greeting"]
        finally:
            _gdb.close()
    except Exception:
        pass

    own_db = False
    if db is None:
        try:
            db_gen = get_db()
            db = next(db_gen)
            own_db = True
        except Exception:
            db = None

    if db is not None:
        try:
            if not customer_id:
                user = st.session_state.get("user", {})
                customer_id = user.get("id")

            if customer_id:
                conv = ConversationService.start_new_session(db, customer_id, restaurant_id)
                st.session_state.active_conversation_id = conv.id

                MessageRepository.create(
                    db=db,
                    conversation_id=conv.id,
                    role="assistant",
                    content=greeting_text
                )
        except Exception as e:
            # Suppress db errors for headless/regression tests with mock dependencies
            print(f"Warning inside initialize_restaurant_conversation: {str(e)}")
        finally:
            if own_db:
                db.close()

    st.session_state.messages = [
        {
            "role": "assistant",
            "content": greeting_text,
            "sources": [],
            "timestamp": datetime.utcnow().isoformat()
        }
    ]


def process_chat_message(db, restaurant_id: str, question: str, conversation_id: str = None, customer_id: str = None) -> dict:
    """
    Lightweight boundary between the presentation layer and ConversationOrchestrator.
    Passing customer_id enables order-status, order-modification, and personalized
    recommendation routing; conversation_id enables escalation persistence.
    """
    from backend.services.conversation_orchestrator import ConversationOrchestrator
    return ConversationOrchestrator.orchestrate(
        db, restaurant_id, question,
        conversation_id=conversation_id, customer_id=customer_id,
    )


def _render_chat_tab(selected_id: str, selected_name: str, user: dict) -> None:
    # Initialize or switch context if context restaurant changed
    if "current_chat_restaurant" not in st.session_state or st.session_state.current_chat_restaurant != selected_id:
        db = next(get_db())
        try:
            customer_id = user.get("id")
            from backend.models.conversation import Conversation
            active_conv = db.query(Conversation).filter(
                Conversation.customer_id == customer_id,
                Conversation.restaurant_id == selected_id,
                Conversation.status == "active"
            ).first()

            if active_conv:
                st.session_state.selected_restaurant = selected_id
                st.session_state.current_chat_restaurant = selected_id
                st.session_state.active_conversation_id = active_conv.id
                history = ConversationService.load_history(db, active_conv.id, customer_id)
                st.session_state.messages = []
                for m in history:
                    st.session_state.messages.append({
                        "role": m.role,
                        "content": m.content,
                        "sources": m.sources or [],
                        "intent": m.intent,
                        "sentiment": m.sentiment,
                        "language": m.language,
                        "escalated": m.escalated,
                        "timestamp": m.timestamp.isoformat()
                    })
            else:
                initialize_restaurant_conversation(selected_id, selected_name, customer_id, db)
        finally:
            db.close()

    # Render message history
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg.get("role") == "assistant" and msg.get("sources"):
                with st.expander("View sources & citations", expanded=False):
                    for idx, src in enumerate(msg["sources"], 1):
                        title = src.get("title", "Unknown Document")
                        doc_type = src.get("document_type", "other").upper()
                        doc_id = src.get("document_id", "N/A")
                        snippet = src.get("snippet", "")
                        st.markdown(f"**[{idx}] {title}** ({doc_type})")
                        st.caption(f"Source ID: `{doc_id}`")
                        if snippet:
                            st.info(snippet)

    # Chat input
    if prompt := st.chat_input(f"Message {selected_name} assistant..."):
        with st.chat_message("user"):
            st.markdown(prompt)
        st.session_state.messages.append({"role": "user", "content": prompt, "timestamp": datetime.utcnow().isoformat()})

        db = next(get_db())
        try:
            MessageRepository.create(db=db, conversation_id=st.session_state.active_conversation_id, role="user", content=prompt)
        finally:
            db.close()

        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                try:
                    db = next(get_db())
                    try:
                        response = process_chat_message(
                            db, selected_id, prompt,
                            conversation_id=st.session_state.active_conversation_id,
                            customer_id=user.get("id"),
                        )
                    finally:
                        db.close()

                    answer_text = response.get("answer", "I could not retrieve a response.")
                    response_sources = response.get("sources", [])

                    typing_speed = st.session_state.get("typing_speed", 0.02)
                    message_placeholder = st.empty()
                    full_response = ""
                    for chunk in answer_text.split(" "):
                        full_response += chunk + " "
                        time.sleep(typing_speed)
                        message_placeholder.markdown(full_response + "▌")
                    message_placeholder.markdown(answer_text)

                    db = next(get_db())
                    try:
                        msg = MessageRepository.create(
                            db=db,
                            conversation_id=st.session_state.active_conversation_id,
                            role="assistant",
                            content=answer_text,
                            intent=response.get("intent"),
                            intent_confidence=response.get("intent_info", {}).get("confidence", 0.0) if isinstance(response.get("intent_info"), dict) else 0.0,
                            sentiment=response.get("sentiment"),
                            sentiment_confidence=response.get("sentiment_info", {}).get("confidence", 0.0) if isinstance(response.get("sentiment_info"), dict) else 0.0,
                            language=response.get("language"),
                            language_code=response.get("language_code"),
                            latency_ms=response.get("latency_ms", 0.0),
                            escalated=response.get("escalation_result", {}).get("escalate", False) if isinstance(response.get("escalation_result"), dict) else False,
                            sources=response_sources
                        )
                        if msg.escalated:
                            ConversationService.update_status(db, st.session_state.active_conversation_id, "escalated")
                    finally:
                        db.close()

                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": answer_text,
                        "sources": response_sources,
                        "intent": response.get("intent"),
                        "sentiment": response.get("sentiment"),
                        "language": response.get("language"),
                        "escalated": response.get("escalation_result", {}).get("escalate", False) if isinstance(response.get("escalation_result"), dict) else False,
                        "timestamp": datetime.utcnow().isoformat()
                    })
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to generate response: {str(e)}")

    # Close Chat and Rate
    st.markdown("<br/>", unsafe_allow_html=True)
    col1, col2 = st.columns([6, 2])
    with col2:
        if st.button("Close Chat & Rate", key="close_chat_btn"):
            st.session_state.show_rating_modal = True

    if st.session_state.get("show_rating_modal", False):
        st.markdown(
            f'<div class="icsa-sec" style="margin-top:.6rem;">{chip("star", 17, 32)}'
            f'<div class="t">Rate your experience</div></div>',
            unsafe_allow_html=True,
        )
        rating = st.slider("CSAT Rating (1 to 5 stars):", min_value=1, max_value=5, value=5)
        feedback_text = st.text_area("Feedback comments (optional):", placeholder="Your comments here...")
        if st.button("Submit Feedback", key="submit_feedback_btn"):
            db = next(get_db())
            try:
                FeedbackService.submit_feedback(
                    db=db, conversation_id=st.session_state.active_conversation_id,
                    rating=rating, feedback_text=feedback_text, customer_id=user.get("id"),
                )
                st.success("Thank you for your feedback!")
                st.session_state.show_rating_modal = False
                for key in ("active_conversation_id", "messages", "current_chat_restaurant"):
                    st.session_state.pop(key, None)
                time.sleep(1.2)
                st.rerun()
            except Exception as e:
                st.error(f"Error submitting feedback: {str(e)}")
            finally:
                db.close()


def _render_menu_tab(selected_id: str, selected_name: str) -> None:
    st.markdown(
        f'<div class="icsa-sec">{chip("menu", 18, 34)}'
        f'<div><div class="t">{selected_name} menu</div>'
        f'<div class="d">Browse dishes, prices, and dietary options</div></div></div>',
        unsafe_allow_html=True,
    )
    db = next(get_db())
    try:
        products = MenuService.list_products(db, selected_id)
    finally:
        db.close()
    if not products:
        st.info("This restaurant hasn't published a structured menu yet. Try asking the assistant in the Chat tab.")
        return

    categories = {}
    for p in products:
        categories.setdefault(p["category"], []).append(p)

    for category, items in categories.items():
        st.markdown(f'<div class="menu-cat">{category}</div>', unsafe_allow_html=True)
        for p in items:
            sizes = p.get("size_prices") or {}
            if sizes:
                price_val = f"from ₹{int(min(sizes.values()))}"
                size_line = '<div class="menu-sizes">' + "   ".join(f"{k} ₹{int(v)}" for k, v in sizes.items()) + "</div>"
            else:
                price_val = f"₹{int(p['base_price'])}"
                size_line = ""
            tags = "".join(f'<span class="tag">{t}</span>' for t in (p.get("dietary_tags") or []))
            popular = (
                f'<span class="pill accent" style="margin-left:6px;">{icon("star", 11)}popular</span>'
                if p.get("is_popular") else ""
            )
            desc = f'<div class="menu-desc">{p.get("description")}</div>' if p.get("description") else ""
            st.markdown(
                f'<div class="menu-item">'
                f'<div class="menu-row"><span class="name">{p["name"]}</span>'
                f'<span class="lead"></span><span class="price">{price_val}</span></div>'
                f'<div style="margin-top:5px;">{tags}{popular}</div>'
                f'{size_line}{desc}'
                f'</div>',
                unsafe_allow_html=True,
            )


def _render_orders_tab(selected_id: str, user: dict) -> None:
    st.markdown(
        f'<div class="icsa-sec">{chip("orders", 18, 34)}'
        f'<div><div class="t">My orders</div>'
        f'<div class="d">Track the status and details of your recent orders</div></div></div>',
        unsafe_allow_html=True,
    )
    customer_id = user.get("id")
    if not customer_id:
        st.info("Sign in to see your orders.")
        return
    db = next(get_db())
    try:
        orders = OrderService.get_customer_orders(db, customer_id)
    finally:
        db.close()
    if not orders:
        st.info("You have no orders yet. Demo orders are seeded for the demo customer account.")
        return

    for o in orders:
        color, label = _STATUS_BADGE.get(o["status"], ("#8C8378", o["status"].title()))
        items_str = ", ".join(f"{i['quantity']}× {i['name']}" + (f" ({i['size']})" if i.get("size") else "") for i in o["items"])
        placed = (o["placed_at"] or "")[:16].replace("T", " ")
        st.markdown(
            f'<div class="icsa-card" style="margin-bottom:10px;">'
            f'<div style="display:flex;justify-content:space-between;align-items:center;">'
            f'<span style="font-weight:700;font-family:var(--font-mono);color:var(--ink);">#{o["order_number"]}</span>'
            f'<span class="pill" style="background:{color}1f;color:{color};">{label}</span></div>'
            f'<div style="color:var(--ink-soft);font-size:.86rem;margin-top:7px;">{items_str}</div>'
            f'<div style="color:var(--muted);font-size:.76rem;margin-top:5px;font-family:var(--font-mono);">{o["order_type"].title()} · ₹{int(o["total"])} · {placed}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )


def render_customer_dashboard():
    """Renders the customer dashboard: chat assistant, menu browser, and order tracker."""
    user = st.session_state.get("user", {})
    first = user.get("first_name") or ""
    last = user.get("last_name") or ""
    display_name = f"{first} {last}".strip() or user.get("email", "Customer")
    role_name = user.get("role", "customer")

    st.markdown(
        f"""
        <div class="icsa-hero" style="display:flex;align-items:center;gap:16px;">
            {chip('concierge', 24, 54, bg='var(--chip-accent)', color='var(--accent)', radius=15)}
            <div>
                <div class="icsa-eyebrow">Support Concierge</div>
                <h2 style="margin:.15rem 0 0;">Welcome back, {display_name}</h2>
                <p style="color:var(--muted);font-size:.9rem;margin:.25rem 0 0;">Chat with a restaurant's assistant, browse its menu, and track your orders — all grounded in that restaurant's own information.</p>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )
    st.markdown("<div style='height:1rem;'></div>", unsafe_allow_html=True)

    db = next(get_db())
    try:
        active_restaurants = RestaurantRepository.list_active(db)
    finally:
        db.close()

    if not active_restaurants:
        st.warning("⚠️ No active restaurants available to chat with.")
        return

    restaurant_options = {r.name: r.id for r in active_restaurants}
    selected_name = st.selectbox(
        "Select Restaurant:",
        options=list(restaurant_options.keys()),
        help="Choose a restaurant to chat with, browse its menu, or track your orders.",
    )
    selected_id = restaurant_options[selected_name]

    tab_chat, tab_menu, tab_orders = st.tabs(["Chat", "Menu", "My Orders"])
    with tab_chat:
        _render_chat_tab(selected_id, selected_name, user)
    with tab_menu:
        _render_menu_tab(selected_id, selected_name)
    with tab_orders:
        _render_orders_tab(selected_id, user)
