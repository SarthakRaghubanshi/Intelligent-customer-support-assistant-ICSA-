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
from components.customer_dashboard import render_customer_dashboard
from components.restaurant_dashboard import render_restaurant_dashboard
from components.admin_dashboard import render_admin_dashboard

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
active_view = st.session_state.get("active_view")

from utils.auth_helper import has_permission

if active_view == "💬 Customer Dashboard":
    if not has_permission("chat:read_write"):
        st.error("Permission Denied")
        st.stop()
    render_customer_dashboard()
elif active_view == "📊 Restaurant Dashboard":
    if not has_permission("analytics:read_own"):
        st.error("Permission Denied")
        st.stop()
    render_restaurant_dashboard()
elif active_view == "⚙️ Admin Dashboard":
    if not has_permission("admin:manage_system"):
        st.error("Permission Denied")
        st.stop()
    render_admin_dashboard()
else:
    st.error("Permission Denied")
    st.stop()

