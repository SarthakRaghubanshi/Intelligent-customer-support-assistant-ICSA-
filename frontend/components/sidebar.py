import streamlit as st
import os
import sys

# Ensure frontend path is added to sys.path so utils imports work reliably
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

from utils.session import clear_chat_history

def render_sidebar():
    """Renders the sidebar navigation and configuration controls."""
    with st.sidebar:
        # App Branding using customized HTML
        st.markdown(
            """
            <div style='text-align: center; margin-top: 1rem; margin-bottom: 2rem;'>
                <h1 style='color: #6C5CE7; font-size: 2.2rem; margin-bottom: 0.2rem; font-weight: 700;'>ICSA</h1>
                <p style='color: rgba(248, 250, 252, 0.6); font-size: 0.85rem; letter-spacing: 1px; font-weight: 300;'>
                    Intelligent Customer Support Assistant
                </p>
                <hr style='border: 0; border-top: 1px solid rgba(255, 255, 255, 0.1); margin: 1.5rem 0;'/>
            </div>
            """,
            unsafe_allow_html=True
        )
        
        # Navigation controls using Streamlit automatic state binding
        st.markdown("### 🧭 Navigation")
        st.selectbox(
            "Go to Page:",
            options=["💬 Chat Assistant", "📊 Analytics Dashboard"],
            key="active_view"
        )
        
        st.markdown("<br/>", unsafe_allow_html=True)
        
        # Restaurant Context Configurator
        st.markdown("### 🍔 Context Settings")
        restaurant_options = ["All Restaurants", "Burgers & Co", "Pizzeria d'Italia", "Sushi Zen", "Taco Fiesta"]
        
        # Update session state based on select box
        st.session_state.selected_restaurant = st.selectbox(
            "Active Restaurant Context:",
            options=restaurant_options,
            index=restaurant_options.index(st.session_state.selected_restaurant),
            help="Sets the context for restaurant-specific menus or policies (mocked for Phase 1)."
        )
        
        st.markdown("<br/>", unsafe_allow_html=True)
        
        # Simulator Settings
        st.markdown("### ⚙️ Simulator Controls")
        
        # Adjustable typing speed delay
        st.session_state.typing_speed = st.slider(
            "Typing Simulation Speed (s):",
            min_value=0.00,
            max_value=0.10,
            value=st.session_state.typing_speed,
            step=0.01,
            help="Controls typing simulation delay for the chatbot's response."
        )
        
        st.markdown("<br/>", unsafe_allow_html=True)
        
        # Clear Chat Button
        st.button(
            "🧹 Clear Conversation",
            use_container_width=True,
            on_click=clear_chat_history,
            type="secondary"
        )
        
        # System status panel with metadata
        st.markdown(
            """
            <div style='margin-top: 3rem; padding: 1.2rem; background-color: rgba(30, 41, 59, 0.4); border-radius: 12px; border: 1px solid rgba(255, 255, 255, 0.05);'>
                <div style='display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.6rem;'>
                    <span style='font-size: 0.8rem; color: rgba(248, 250, 252, 0.6);'>Core Status</span>
                    <span style='font-size: 0.75rem; color: #10B981; font-weight: bold;'>● Online</span>
                </div>
                <div style='display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.6rem;'>
                    <span style='font-size: 0.8rem; color: rgba(248, 250, 252, 0.6);'>Version</span>
                    <span style='font-size: 0.75rem; color: #6C5CE7; font-weight: bold;'>1.0.0 (UI)</span>
                </div>
                <div style='display: flex; justify-content: space-between; align-items: center;'>
                    <span style='font-size: 0.8rem; color: rgba(248, 250, 252, 0.6);'>AI Engine</span>
                    <span style='font-size: 0.75rem; color: rgba(248, 250, 252, 0.4);'>Mock Responses</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )
