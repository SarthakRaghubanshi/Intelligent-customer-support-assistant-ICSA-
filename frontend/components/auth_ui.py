import streamlit as st
from backend.models.user import UserRole
from utils.auth_helper import login_user, register_user
from utils.icons import icon

def render_auth_ui():
    """Renders the ICSA sign-in / registration screen."""
    # Narrow, centered auth layout + light form styling for this page only.
    st.markdown(
        """
        <style>
        .stMain .block-container, [data-testid="stMainBlockContainer"] { max-width: 540px !important; }
        div[data-testid="stForm"] {
            background: var(--surface) !important;
            border: 1px solid var(--line) !important;
            border-radius: 18px !important;
            padding: 2rem !important;
            box-shadow: var(--shadow) !important;
            margin-bottom: 1.5rem !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # Brand lockup
    st.markdown(
        f"""
        <div style='text-align:center; margin-top:1.4rem; margin-bottom:1.8rem;'>
            <span style='display:inline-flex; align-items:center; justify-content:center; width:64px; height:64px; border-radius:18px; background:var(--accent); color:#fff; box-shadow:0 10px 26px rgba(225,74,43,.30); margin-bottom:.9rem;'>{icon('concierge', 30)}</span>
            <h1 style='font-family:var(--font-display); font-size:2.3rem; margin:0; letter-spacing:-0.03em; color:var(--ink);'>ICSA</h1>
            <p style='color:var(--muted); font-size:.85rem; margin-top:.35rem;'>AI Support Concierge for multi-restaurant ordering</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Streamlit Tab Layout
    tab_login, tab_register = st.tabs(["Sign in", "Create account"])

    # --- Login Tab ---
    with tab_login:
        st.markdown("<h4 style='margin-bottom:0.3rem;'>Welcome back</h4>", unsafe_allow_html=True)
        st.markdown("<p style='color:var(--muted); font-size:0.85rem; margin-bottom:1.3rem;'>Sign in to reach your support workspace.</p>", unsafe_allow_html=True)

        with st.form("login_form"):
            email = st.text_input("Email address", placeholder="name@example.com").strip()
            password = st.text_input("Password", type="password", placeholder="••••••••")

            submit = st.form_submit_button("Sign in", use_container_width=True, type="primary")
            
            if submit:
                if not email or not password:
                    st.error("Please enter both email and password.")
                else:
                    success, msg = login_user(email, password)
                    if success:
                        st.success("Successfully authenticated. Logging in...")
                        st.rerun()
                    else:
                        st.error(f"Authentication failed: {msg}")

    # --- Registration Tab ---
    with tab_register:
        st.markdown("<h4 style='margin-bottom:0.3rem;'>Create your account</h4>", unsafe_allow_html=True)
        st.markdown("<p style='color:var(--muted); font-size:0.85rem; margin-bottom:1.3rem;'>Join as a customer, or register your restaurant.</p>", unsafe_allow_html=True)
        
        # Unwrapped from st.form to enable dynamic fields rendering on widget selection changes
        reg_email = st.text_input("Email Address", placeholder="name@example.com", key="reg_email").strip()
        reg_password = st.text_input("Password (minimum 8 characters)", type="password", placeholder="••••••••", key="reg_password")
        reg_confirm = st.text_input("Confirm Password", type="password", placeholder="••••••••", key="reg_confirm")
        
        col1, col2 = st.columns(2)
        with col1:
            first_name = st.text_input("First Name (Optional)", placeholder="John", key="reg_first_name").strip()
        with col2:
            last_name = st.text_input("Last Name (Optional)", placeholder="Doe", key="reg_last_name").strip()
            
        role_label = st.selectbox(
            "Select Account Role",
            options=["Customer Support User", "Restaurant Manager"],
            index=0,
            key="reg_role_label"
        )
        
        # Map selected human readable label to the standard UserRole model enum values
        role_map = {
            "Customer Support User": UserRole.CUSTOMER,
            "Restaurant Manager": UserRole.RESTAURANT,
        }
        selected_role = role_map[role_label]
        
        restaurant_name_input = None
        
        if selected_role == UserRole.RESTAURANT:
            restaurant_name_input = st.text_input("Restaurant Name", placeholder="e.g. Bella Italia", key="reg_new_rest_name").strip()
        
        register_submit = st.button("Create account", key="register_submit_btn", use_container_width=True, type="primary")
        
        if register_submit:
            if not reg_email or not reg_password:
                st.error("Please fill in email and password fields.")
            elif len(reg_password) < 8:
                st.error("Password must be at least 8 characters.")
            elif reg_password != reg_confirm:
                st.error("Passwords do not match.")
            elif selected_role == UserRole.RESTAURANT and not restaurant_name_input:
                st.error("⚠️ Please specify a restaurant name.")
            else:
                success, msg = register_user(
                    email=reg_email,
                    password_raw=reg_password,
                    role=selected_role,
                    first_name=first_name,
                    last_name=last_name,
                    restaurant_name=restaurant_name_input
                )
                if success:
                    st.success(msg)
                else:
                    st.error(f"Registration failed: {msg}")

    # Demo credentials hint for reviewers
    st.markdown(
        f"""
        <div class="icsa-card" style="padding:.9rem 1rem; margin-top:.5rem;">
            <div style="display:flex; align-items:center; gap:8px; color:var(--ink-soft); font-weight:600; font-size:.82rem; margin-bottom:.4rem;">
                {icon('sparkles', 14, 'var(--accent)')} Demo accounts
            </div>
            <div style="color:var(--muted); font-size:.78rem; line-height:1.7; font-family:var(--font-mono);">
                customer@icsa.com · Customer123!<br>
                manager.pizza@icsa.com · Manager123!<br>
                admin@icsa.com · AdminPass123!
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
