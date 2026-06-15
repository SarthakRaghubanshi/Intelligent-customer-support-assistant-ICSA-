import streamlit as st
import time
import os
import sys

# Ensure the frontend and root directories are in the python path
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(current_dir)
if current_dir not in sys.path:
    sys.path.append(current_dir)
if root_dir not in sys.path:
    sys.path.append(root_dir)

from utils.session import init_session_state
from components.sidebar import render_sidebar
from backend.gemini_service import generate_response
from components.dashboard import render_dashboard

# Set up page configurations
st.set_page_config(
    page_title="ICSA - Customer Support",
    page_icon="💬",
    layout="centered",
    initial_sidebar_state="expanded"
)

# Load custom CSS
def load_css(file_path):
    if os.path.exists(file_path):
        with open(file_path, "r") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# CSS is located in the same directory as app.py
css_path = os.path.join(current_dir, "styles.css")
load_css(css_path)

# Initialize Session State
init_session_state()

# Authentication Guard
from utils.auth_helper import init_auth_session_state, check_auth
from components.auth_ui import render_auth_ui

init_auth_session_state()
if not check_auth():
    render_auth_ui()
    st.stop()

# Render Sidebar Components
render_sidebar()

# Main Header Interface
active_view = st.session_state.get("active_view", "💬 Chat Assistant")

if active_view == "💬 Chat Assistant":
    st.markdown(
        """
        <div style='display: flex; align-items: center; gap: 16px; margin-bottom: 2rem;'>
            <div style='background: linear-gradient(135deg, #6C5CE7, #8A2BE2); padding: 12px; border-radius: 14px; display: inline-flex; box-shadow: 0 4px 15px rgba(108, 92, 231, 0.3);'>
                <span style='font-size: 1.6rem; color: white;'>💬</span>
            </div>
            <div>
                <h2 style='margin: 0; font-size: 1.8rem; font-weight: 600; color: #F8FAFC;'>Intelligent Customer Support</h2>
                <p style='margin: 0; font-size: 0.85rem; color: rgba(248, 250, 252, 0.5); font-weight: 300;'>
                    Ask about order status, restaurant policies, menus, and more.
                </p>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

def render_escalation_banner(reason: str):
    """Renders a simple, professional escalation notification banner."""
    st.markdown(
        f"""
        <div class="escalation-banner">
            <div style="font-weight: 600; margin-bottom: 4px; display: flex; align-items: center; gap: 6px;">
                <span>⚠️</span> Support Team Notified
            </div>
            <div style="font-weight: 500; margin-bottom: 2px;">Reason: {reason}</div>
            <div style="opacity: 0.7; font-size: 0.95em;">This conversation has been flagged for human review.</div>
        </div>
        """,
        unsafe_allow_html=True
    )

if active_view == "💬 Chat Assistant":
    # Render Chat History
    # We loop through messages stored in session state and display them natively
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            # Safe lookup for escalation metadata to ensure backward compatibility
            escalation = message.get("escalation")
            if message.get("role") == "assistant" and escalation and escalation.get("escalate"):
                render_escalation_banner(escalation.get("reason"))

    # User Message Input Area
    if prompt := st.chat_input("Type your message here..."):
        # 1. Store the user's message in session state
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        # 2. Instantly display user's message in the chat history
        with st.chat_message("user"):
            st.markdown(prompt)
            
        # 3. Call the Gemini service to generate a response (with full error handling)
        escalation_data = {"escalate": False, "reason": "No Escalation Required"}
        try:
            # Request full structured dictionary response including escalation metadata
            response_data = generate_response(
                prompt,
                restaurant_id=st.session_state.selected_restaurant,
                return_dict=True
            )
            response_text = response_data["response"]
            escalation_data = response_data["escalation"]
        except Exception as e:
            response_text = f"⚠️ **Error:** {str(e)}"
        
        # 4. Display assistant placeholder and render the response with a typing animation
        with st.chat_message("assistant"):
            message_placeholder = st.empty()
            full_response = ""
            
            # Split words to render typing effect smoothly
            words = response_text.split(" ")
            for index, word in enumerate(words):
                full_response += word + (" " if index < len(words) - 1 else "")
                # Show a pulsing typing cursor block
                message_placeholder.markdown(full_response + "▌")
                # Dynamic delay control from sidebar simulator setting
                time.sleep(st.session_state.typing_speed)
                
            # Display the final complete response without cursor
            message_placeholder.markdown(full_response)
            
            # Immediately render escalation banner if triggered
            if escalation_data.get("escalate"):
                render_escalation_banner(escalation_data.get("reason"))
            
        # 5. Save the assistant's response to session state with escalation metadata
        st.session_state.messages.append({
            "role": "assistant",
            "content": response_text,
            "escalation": escalation_data
        })
else:
    # Render Dashboard view
    render_dashboard()
