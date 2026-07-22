import streamlit as st
import os
import sys

# Ensure frontend path is added to sys.path so utils imports work reliably
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

from utils.session import clear_chat_history
from utils.icons import icon, chip

# role -> (internal active_view key used by app.py, workspace label, icon key)
_WORKSPACE = {
    "admin": ("⚙️ Admin Dashboard", "Admin Console", "admin"),
    "restaurant": ("📊 Restaurant Dashboard", "Restaurant Console", "dashboard"),
    "customer": ("💬 Customer Dashboard", "Customer Workspace", "chat"),
}


def render_sidebar():
    """Renders the sidebar: brand lockup, workspace indicator, and account controls."""
    with st.sidebar:
        # --- Brand lockup ---
        st.markdown(
            f"""
            <div class="icsa-brand">
                <span class="mark">{icon('concierge', 22)}</span>
                <div>
                    <div class="word">ICSA</div>
                    <div class="sub">Support Concierge</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        user = st.session_state.get("user", {})
        role = str(user.get("role", "customer")).strip().lower()
        view_key, ws_label, ws_icon = _WORKSPACE.get(role, _WORKSPACE["customer"])

        # One workspace per role — set the route directly (no redundant dropdown).
        st.session_state.active_view = view_key

        st.markdown(
            f"""
            <div class="icsa-card" style="display:flex;align-items:center;gap:12px;padding:.75rem .9rem;margin-bottom:1rem;">
                {chip(ws_icon, 18, 36)}
                <div>
                    <div style="font-weight:700;font-size:.95rem;color:var(--ink);line-height:1.1;">{ws_label}</div>
                    <div style="color:var(--muted);font-size:.68rem;text-transform:uppercase;letter-spacing:.09em;margin-top:2px;">{role} access</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Admin-only: typing simulation control
        if role == "admin":
            with st.expander("Assistant simulator", expanded=False):
                st.session_state.typing_speed = st.slider(
                    "Typing speed (seconds/word)", min_value=0.00, max_value=0.10,
                    value=st.session_state.get("typing_speed", 0.02), step=0.01,
                )

        st.button("Clear conversation", use_container_width=True, on_click=clear_chat_history)

        st.markdown("<div style='height:0.6rem;'></div>", unsafe_allow_html=True)

        # --- Account ---
        if user:
            first = user.get("first_name") or ""
            last = user.get("last_name") or ""
            display_name = f"{first} {last}".strip() or user.get("email")
            st.markdown(
                f"""
                <div class="icsa-card" style="display:flex;align-items:center;gap:11px;padding:.8rem .9rem;">
                    {chip('user', 18, 36, bg='var(--chip)', color='var(--ink-soft)')}
                    <div style="min-width:0;">
                        <div style="font-weight:600;font-size:.88rem;color:var(--ink);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">{display_name}</div>
                        <div style="color:var(--muted);font-size:.72rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">{user.get('email')}</div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            from utils.auth_helper import logout_user
            if st.button("Log out", use_container_width=True):
                logout_user()

        # --- System status ---
        st.markdown(
            f"""
            <div class="icsa-card" style="padding:.85rem .9rem;margin-top:1rem;">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:.5rem;">
                    <span style="font-size:.76rem;color:var(--muted);">Status</span>
                    <span style="font-size:.74rem;color:var(--success);font-weight:600;display:inline-flex;align-items:center;gap:5px;">
                        <span style="width:7px;height:7px;border-radius:50%;background:var(--success);display:inline-block;"></span>Online
                    </span>
                </div>
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:.5rem;">
                    <span style="font-size:.76rem;color:var(--muted);">AI engine</span>
                    <span style="font-size:.74rem;color:var(--ink-soft);font-weight:600;display:inline-flex;align-items:center;gap:6px;">
                        {icon('sparkles', 13, 'var(--accent)')} Google Gemini
                    </span>
                </div>
                <div style="display:flex;justify-content:space-between;align-items:center;">
                    <span style="font-size:.76rem;color:var(--muted);">Version</span>
                    <span style="font-size:.74rem;color:var(--ink-soft);font-weight:600;font-family:var(--font-mono);">1.0.0</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
