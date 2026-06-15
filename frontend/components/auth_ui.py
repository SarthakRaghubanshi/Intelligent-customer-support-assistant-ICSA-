import streamlit as st
from backend.models.user import UserRole
from utils.auth_helper import login_user, register_user

def render_auth_ui():
    """
    Renders a premium, glassmorphic login and registration tabbed interface.
    """
    # Centered logo and title branding
    st.markdown(
        """
        <div style='text-align: center; margin-top: 1.5rem; margin-bottom: 2.5rem;'>
            <div style='background: linear-gradient(135deg, #6C5CE7, #8A2BE2); width: 64px; height: 64px; border-radius: 18px; display: inline-flex; align-items: center; justify-content: center; box-shadow: 0 8px 25px rgba(108, 92, 231, 0.4); margin-bottom: 1rem;'>
                <span style='font-size: 2.2rem; color: white;'>💬</span>
            </div>
            <h1 style='background: linear-gradient(135deg, #F8FAFC, #94A3B8); -webkit-background-clip: text; -webkit-text-fill-color: transparent; font-size: 2.4rem; margin: 0; font-weight: 700;'>ICSA Portal</h1>
            <p style='color: rgba(248, 250, 252, 0.5); font-size: 0.9rem; letter-spacing: 1px; font-weight: 300; margin-top: 0.4rem;'>
                Intelligent Customer Support Assistant
            </p>
        </div>
        """,
        unsafe_allow_html=True
    )

    # CSS to inject for styling Streamlit forms and input widgets to match premium design system
    st.markdown(
        """
        <style>
        /* Form container premium styling */
        div[data-testid="stForm"] {
            background-color: rgba(15, 23, 42, 0.6) !important;
            border: 1px solid rgba(255, 255, 255, 0.06) !important;
            border-radius: 20px !important;
            padding: 2.5rem !important;
            backdrop-filter: blur(12px) !important;
            box-shadow: 0 12px 30px rgba(0, 0, 0, 0.3) !important;
            margin-bottom: 2rem !important;
        }
        
        /* Premium custom styling for Form Buttons */
        div[data-testid="stForm"] button[kind="primaryFormSubmit"],
        div[data-testid="stForm"] button[kind="secondaryFormSubmit"] {
            background: linear-gradient(135deg, #6C5CE7, #8A2BE2) !important;
            color: #F8FAFC !important;
            border: none !important;
            border-radius: 10px !important;
            padding: 0.6rem 2rem !important;
            font-weight: 600 !important;
            font-size: 0.95rem !important;
            transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1) !important;
            box-shadow: 0 4px 15px rgba(108, 92, 231, 0.25) !important;
            cursor: pointer !important;
        }
        
        div[data-testid="stForm"] button[kind="primaryFormSubmit"]:hover,
        div[data-testid="stForm"] button[kind="secondaryFormSubmit"]:hover {
            transform: translateY(-2px) !important;
            box-shadow: 0 6px 20px rgba(108, 92, 231, 0.45) !important;
            color: #FFFFFF !important;
        }

        div[data-testid="stForm"] button[kind="primaryFormSubmit"]:active,
        div[data-testid="stForm"] button[kind="secondaryFormSubmit"]:active {
            transform: translateY(0) !important;
        }
        
        /* Input borders */
        div[data-testid="stForm"] input, 
        div[data-testid="stForm"] select, 
        div[data-testid="stForm"] div[data-baseweb="select"] {
            border-radius: 8px !important;
        }
        </style>
        """,
        unsafe_allow_html=True
    )

    # Streamlit Tab Layout
    tab_login, tab_register = st.tabs(["🔑 Sign In", "📝 Create Account"])

    # --- Login Tab ---
    with tab_login:
        st.markdown("<h4 style='color: #F8FAFC; margin-bottom: 0.5rem;'>Sign In</h4>", unsafe_allow_html=True)
        st.markdown("<p style='color: rgba(248,250,252,0.4); font-size: 0.85rem; margin-bottom: 1.5rem;'>Welcome back. Authenticate to access customer support contexts.</p>", unsafe_allow_html=True)
        
        with st.form("login_form"):
            email = st.text_input("Email Address", placeholder="name@example.com").strip()
            password = st.text_input("Password", type="password", placeholder="••••••••")
            
            submit = st.form_submit_button("Sign In", use_container_width=True)
            
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
        st.markdown("<h4 style='color: #F8FAFC; margin-bottom: 0.5rem;'>Create Account</h4>", unsafe_allow_html=True)
        st.markdown("<p style='color: rgba(248,250,252,0.4); font-size: 0.85rem; margin-bottom: 1.5rem;'>Sign up to deploy custom assistant agents.</p>", unsafe_allow_html=True)
        
        with st.form("registration_form"):
            reg_email = st.text_input("Email Address", placeholder="name@example.com").strip()
            reg_password = st.text_input("Password (minimum 8 characters)", type="password", placeholder="••••••••")
            reg_confirm = st.text_input("Confirm Password", type="password", placeholder="••••••••")
            
            col1, col2 = st.columns(2)
            with col1:
                first_name = st.text_input("First Name (Optional)", placeholder="John").strip()
            with col2:
                last_name = st.text_input("Last Name (Optional)", placeholder="Doe").strip()
                
            role_label = st.selectbox(
                "Select Account Role",
                options=["Customer Support User", "Restaurant Manager", "System Administrator"],
                index=0
            )
            
            # Map selected human readable label to the standard UserRole model enum values
            role_map = {
                "Customer Support User": UserRole.CUSTOMER,
                "Restaurant Manager": UserRole.RESTAURANT,
                "System Administrator": UserRole.ADMIN
            }
            selected_role = role_map[role_label]
            
            register_submit = st.form_submit_button("Create Account", use_container_width=True)
            
            if register_submit:
                if not reg_email or not reg_password:
                    st.error("Please fill in email and password fields.")
                elif len(reg_password) < 8:
                    st.error("Password must be at least 8 characters.")
                elif reg_password != reg_confirm:
                    st.error("Passwords do not match.")
                else:
                    success, msg = register_user(
                        email=reg_email,
                        password_raw=reg_password,
                        role=selected_role,
                        first_name=first_name,
                        last_name=last_name
                    )
                    if success:
                        st.success(msg)
                    else:
                        st.error(f"Registration failed: {msg}")
