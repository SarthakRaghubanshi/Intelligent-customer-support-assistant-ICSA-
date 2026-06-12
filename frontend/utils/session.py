import streamlit as st

def init_session_state():
    """Initializes the session state variables for the chatbot interface."""
    # Initialize chat message history
    if "messages" not in st.session_state:
        st.session_state.messages = [
            {
                "role": "assistant",
                "content": "Hello! I am your Intelligent Customer Support Assistant (ICSA). How can I assist you with your restaurant or order queries today?"
            }
        ]
    
    # Initialize active restaurant context
    if "selected_restaurant" not in st.session_state:
        st.session_state.selected_restaurant = "Restaurant_A"
        
    # Initialize response typing speed setting
    if "typing_speed" not in st.session_state:
        st.session_state.typing_speed = 0.02


def clear_chat_history():
    """Resets the chat message history to the initial state."""
    st.session_state.messages = [
        {
            "role": "assistant",
            "content": "Chat history cleared. How can I assist you now?"
        }
    ]
