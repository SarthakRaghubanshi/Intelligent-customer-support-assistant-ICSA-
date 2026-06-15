import streamlit as st

def render_customer_dashboard():
    """
    Renders the customer dashboard shell structure.
    """
    user = st.session_state.get("user", {})
    first = user.get("first_name") or ""
    last = user.get("last_name") or ""
    display_name = f"{first} {last}".strip() or user.get("email", "Customer")
    role_name = user.get("role", "customer")

    st.markdown(
        f"""
        <div style='background: linear-gradient(135deg, rgba(108, 92, 231, 0.1), rgba(138, 43, 226, 0.15)); padding: 2.5rem; border-radius: 20px; border: 1px solid rgba(108, 92, 231, 0.25); text-align: center; margin-top: 2rem; box-shadow: 0 8px 32px rgba(0, 0, 0, 0.15);'>
            <div style='font-size: 3.5rem; margin-bottom: 1rem;'>👋</div>
            <h2 style='margin: 0; font-size: 2rem; font-weight: 700; color: #F8FAFC;'>Welcome, {display_name}!</h2>
            <p style='color: rgba(248, 250, 252, 0.6); font-size: 1rem; margin-top: 0.5rem; font-weight: 300;'>
                Account Role: <span style='background-color: #6C5CE7; color: white; padding: 2px 8px; border-radius: 12px; font-size: 0.8rem; font-weight: 600; text-transform: uppercase;'>{role_name}</span>
            </p>
            <hr style='border: 0; border-top: 1px solid rgba(255, 255, 255, 0.1); margin: 2rem 0;'/>
            <div style='background-color: rgba(15, 23, 42, 0.4); padding: 1.5rem; border-radius: 12px; border: 1px solid rgba(255, 255, 255, 0.05); display: inline-block;'>
                <h4 style='margin: 0; color: #6C5CE7; font-weight: 600;'>💬 Chat Assistant Coming Soon</h4>
                <p style='margin: 8px 0 0 0; color: rgba(248, 250, 252, 0.5); font-size: 0.85rem;'>
                    Our AI-powered customer support chat system is currently under preparation.
                </p>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )
