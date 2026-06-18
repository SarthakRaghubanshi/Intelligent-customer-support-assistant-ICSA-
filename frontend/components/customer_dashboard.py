import streamlit as st
import time
from datetime import datetime
from backend.database.database import get_db
from backend.repositories.restaurant_repository import RestaurantRepository

def initialize_restaurant_conversation(restaurant_id: str, restaurant_name: str) -> None:
    """
    Resets conversation history, sets restaurant-specific greeting with UTC timestamp,
    and updates active and current restaurant session state trackers.
    """
    st.session_state.selected_restaurant = restaurant_id
    st.session_state.current_chat_restaurant = restaurant_id
    
    st.session_state.messages = [
        {
            "role": "assistant",
            "content": f"Hello! I am your Intelligent Customer Support Assistant for {restaurant_name}. How can I help you today?",
            "sources": [],
            "timestamp": datetime.utcnow().isoformat()
        }
    ]

def process_chat_message(db, restaurant_id: str, question: str) -> dict:
    """
    Lightweight boundary between the presentation layer and ConversationOrchestrator.
    Avoids direct LLM calling or custom route bypassing.
    """
    from backend.services.conversation_orchestrator import ConversationOrchestrator
    return ConversationOrchestrator.orchestrate(db, restaurant_id, question)

def render_customer_dashboard():
    """
    Renders the customer dashboard featuring the interactive Chat Assistant UI.
    """
    user = st.session_state.get("user", {})
    first = user.get("first_name") or ""
    last = user.get("last_name") or ""
    display_name = f"{first} {last}".strip() or user.get("email", "Customer")
    role_name = user.get("role", "customer")

    # App Branding Card
    st.markdown(
        f"""
        <div style='background: linear-gradient(135deg, rgba(108, 92, 231, 0.1), rgba(138, 43, 226, 0.15)); padding: 2rem; border-radius: 20px; border: 1px solid rgba(108, 92, 231, 0.25); text-align: center; margin-top: 1.5rem; box-shadow: 0 8px 32px rgba(0, 0, 0, 0.15);'>
            <div style='font-size: 3rem; margin-bottom: 0.5rem;'>👋</div>
            <h2 style='margin: 0; font-size: 1.8rem; font-weight: 700; color: #F8FAFC;'>Welcome, {display_name}!</h2>
            <p style='color: rgba(248, 250, 252, 0.6); font-size: 0.95rem; margin-top: 0.3rem; font-weight: 300; margin-bottom: 0;'>
                Account Role: <span style='background-color: #6C5CE7; color: white; padding: 2px 8px; border-radius: 12px; font-size: 0.75rem; font-weight: 600; text-transform: uppercase;'>{role_name}</span>
            </p>
        </div>
        """,
        unsafe_allow_html=True
    )

    st.markdown("<br/>", unsafe_allow_html=True)

    # 1. Fetch active restaurants context
    db_gen = get_db()
    db = next(db_gen)
    try:
        active_restaurants = RestaurantRepository.list_active(db)
    finally:
        db.close()

    if not active_restaurants:
        st.warning("⚠️ No active restaurants available to chat with.")
        return

    # Map name options to database UUIDs
    restaurant_options = {r.name: r.id for r in active_restaurants}
    
    # 2. Render Context Selector Dropdown
    selected_name = st.selectbox(
        "Select Restaurant to Chat with:",
        options=list(restaurant_options.keys()),
        help="Choose a restaurant to consult about their menu, business hours, and delivery terms."
    )
    selected_id = restaurant_options[selected_name]

    # Initialize or switch context if context restaurant changed
    if "current_chat_restaurant" not in st.session_state or st.session_state.current_chat_restaurant != selected_id:
        initialize_restaurant_conversation(selected_id, selected_name)

    st.markdown("---")

    # 3. Render Message History logs
    # Filter messages to ensure we only display assistant/user messages
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # 4. Handle chat input controls
    if prompt := st.chat_input(f"Message {selected_name} assistant..."):
        # Display user input immediately
        with st.chat_message("user"):
            st.markdown(prompt)
            
        # Append User Message with timestamp
        st.session_state.messages.append({
            "role": "user",
            "content": prompt,
            "timestamp": datetime.utcnow().isoformat()
        })

        # Process and display assistant response
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                try:
                     db_gen = get_db()
                     db = next(db_gen)
                     try:
                         response = process_chat_message(db, selected_id, prompt)
                     finally:
                         db.close()
                         
                     answer_text = response.get("answer", "I could not retrieve a response.")
                     response_sources = response.get("sources", [])

                     # Render simulated typing delay effect
                     typing_speed = st.session_state.get("typing_speed", 0.02)
                     message_placeholder = st.empty()
                     
                     full_response = ""
                     # Simple typewriter simulation by split spaces
                     for chunk in answer_text.split(" "):
                         full_response += chunk + " "
                         time.sleep(typing_speed)
                         message_placeholder.markdown(full_response + "▌")
                     message_placeholder.markdown(answer_text)

                     # Append assistant message with UI-facing fields and timestamp
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
                     
                     # Force UI refresh to update state
                     st.rerun()
                     
                except Exception as e:
                     st.error(f"Failed to generate response: {str(e)}")
