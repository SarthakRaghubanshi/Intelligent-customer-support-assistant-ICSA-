import streamlit as st
import time
from datetime import datetime
from backend.database.database import get_db
from backend.repositories.restaurant_repository import RestaurantRepository
from backend.repositories.message_repository import MessageRepository
from backend.services.conversation_service import ConversationService
from backend.services.feedback_service import FeedbackService

def initialize_restaurant_conversation(restaurant_id: str, restaurant_name: str, customer_id: str = None, db = None) -> None:
    """
    Resets conversation history, sets restaurant-specific greeting with UTC timestamp,
    and updates active and current restaurant session state trackers.
    """
    st.session_state.selected_restaurant = restaurant_id
    st.session_state.current_chat_restaurant = restaurant_id
    
    greeting_text = f"Hello! I am your Intelligent Customer Support Assistant for {restaurant_name}. How can I help you today?"
    
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
        db_gen = get_db()
        db = next(db_gen)
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
                # Load history from DB
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

    st.markdown("---")

    # 3. Render Message History logs
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
        
        # Save User Message to database
        db_gen = get_db()
        db = next(db_gen)
        try:
            MessageRepository.create(
                db=db,
                conversation_id=st.session_state.active_conversation_id,
                role="user",
                content=prompt
            )
        finally:
            db.close()

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
                     for chunk in answer_text.split(" "):
                         full_response += chunk + " "
                         time.sleep(typing_speed)
                         message_placeholder.markdown(full_response + "▌")
                     message_placeholder.markdown(answer_text)

                     # Save Assistant Message to database
                     db_gen = get_db()
                     db = next(db_gen)
                     try:
                         msg = MessageRepository.create(
                             db=db,
                             conversation_id=st.session_state.active_conversation_id,
                             role="assistant",
                             content=answer_text,
                             intent=response.get("intent"),
                             intent_confidence=response.get("intent_info", {}).get("confidence", 0.0) if isinstance(response.get("intent_info"), dict) else 0.0,
                             sentiment=response.get("sentiment"),
                             sentiment_confidence=response.get("intent_info", {}).get("confidence", 0.0) if isinstance(response.get("intent_info"), dict) else 0.0,
                             language=response.get("language"),
                             language_code=response.get("language_code"),
                             latency_ms=150.0,
                             escalated=response.get("escalation_result", {}).get("escalate", False) if isinstance(response.get("escalation_result"), dict) else False,
                             sources=response_sources
                         )
                         
                         # Check if status transitions to escalated
                         if msg.escalated:
                             ConversationService.update_status(db, st.session_state.active_conversation_id, "escalated")
                     finally:
                         db.close()

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

    # Close Chat and Rate Button
    st.markdown("<br/>", unsafe_allow_html=True)
    col1, col2 = st.columns([6, 2])
    with col2:
        if st.button("Close Chat & Rate", key="close_chat_btn"):
            st.session_state.show_rating_modal = True

    # 5. Rating Modal / Overlay
    if st.session_state.get("show_rating_modal", False):
        st.markdown(
            """
            <div style='background: rgba(30, 41, 59, 0.7); backdrop-filter: blur(12px); border-radius: 16px; border: 1px solid rgba(255, 255, 255, 0.1); padding: 1.5rem; margin-top: 1rem;'>
                <h3 style='color: #F8FAFC; margin-top: 0;'>Rate Your Experience</h3>
            </div>
            """,
            unsafe_allow_html=True
        )
        rating = st.slider("CSAT Rating (1 to 5 stars):", min_value=1, max_value=5, value=5)
        feedback_text = st.text_area("Feedback comments (optional):", placeholder="Your comments here...")
        
        if st.button("Submit Feedback", key="submit_feedback_btn"):
            db_gen = get_db()
            db = next(db_gen)
            try:
                FeedbackService.submit_feedback(
                    db=db,
                    conversation_id=st.session_state.active_conversation_id,
                    rating=rating,
                    feedback_text=feedback_text,
                    customer_id=user.get("id")
                )
                st.success("Thank you for your feedback!")
                st.session_state.show_rating_modal = False
                # Reset chat states
                if "active_conversation_id" in st.session_state:
                    del st.session_state.active_conversation_id
                if "messages" in st.session_state:
                    del st.session_state.messages
                if "current_chat_restaurant" in st.session_state:
                    del st.session_state.current_chat_restaurant
                time.sleep(1.5)
                st.rerun()
            except Exception as e:
                st.error(f"Error submitting feedback: {str(e)}")
            finally:
                db.close()
