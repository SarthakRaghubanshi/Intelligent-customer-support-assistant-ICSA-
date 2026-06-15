import streamlit as st
import pandas as pd
from backend.database.database import get_db
from backend.services.analytics_service import AnalyticsService

def render_restaurant_dashboard():
    """
    Renders the restaurant dashboard with tenant-aware analytics.
    """
    user = st.session_state.get("user", {})
    first = user.get("first_name") or ""
    last = user.get("last_name") or ""
    display_name = f"{first} {last}".strip() or user.get("email", "Restaurant Manager")
    role_name = user.get("role", "restaurant")

    # App Branding using customized HTML
    st.markdown(
        f"""
        <div style='background: linear-gradient(135deg, rgba(16, 185, 129, 0.1), rgba(108, 92, 231, 0.15)); padding: 2.5rem; border-radius: 20px; border: 1px solid rgba(16, 185, 129, 0.25); text-align: center; margin-top: 2rem; box-shadow: 0 8px 32px rgba(0, 0, 0, 0.15);'>
            <div style='font-size: 3.5rem; margin-bottom: 1rem;'>🏪</div>
            <h2 style='margin: 0; font-size: 2rem; font-weight: 700; color: #F8FAFC;'>Welcome, {display_name}!</h2>
            <p style='color: rgba(248, 250, 252, 0.6); font-size: 1rem; margin-top: 0.5rem; font-weight: 300;'>
                Account Role: <span style='background-color: #10B981; color: white; padding: 2px 8px; border-radius: 12px; font-size: 0.8rem; font-weight: 600; text-transform: uppercase;'>{role_name}</span>
            </p>
        </div>
        """,
        unsafe_allow_html=True
    )

    st.markdown("<br/>", unsafe_allow_html=True)
    st.markdown("### 📊 Business Performance Analytics")

    db_gen = get_db()
    db = next(db_gen)
    try:
        restaurant_id = user.get("restaurant_id")
        token = st.session_state.get("access_token")

        if not restaurant_id:
            st.warning("⚠️ No Restaurant Tenant assigned to this account.")
        else:
            analytics = AnalyticsService.get_restaurant_analytics(db, token, restaurant_id)
            
            # Premium Glassmorphic Cards using Streamlit columns
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.markdown(
                    f"""
                    <div style='background: rgba(255, 255, 255, 0.05); padding: 1.2rem; border-radius: 16px; border: 1px solid rgba(255, 255, 255, 0.08); text-align: center;'>
                        <div style='font-size: 0.8rem; color: rgba(248, 250, 252, 0.6); text-transform: uppercase; font-weight: 500;'>Total Tickets</div>
                        <div style='font-size: 2rem; font-weight: 700; color: #6C5CE7; margin-top: 0.4rem;'>{analytics["total_tickets"]}</div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
            with col2:
                st.markdown(
                    f"""
                    <div style='background: rgba(255, 255, 255, 0.05); padding: 1.2rem; border-radius: 16px; border: 1px solid rgba(255, 255, 255, 0.08); text-align: center;'>
                        <div style='font-size: 0.8rem; color: rgba(248, 250, 252, 0.6); text-transform: uppercase; font-weight: 500;'>CSAT Score</div>
                        <div style='font-size: 2rem; font-weight: 700; color: #10B981; margin-top: 0.4rem;'>{analytics["csat"]} / 5</div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
            with col3:
                st.markdown(
                    f"""
                    <div style='background: rgba(255, 255, 255, 0.05); padding: 1.2rem; border-radius: 16px; border: 1px solid rgba(255, 255, 255, 0.08); text-align: center;'>
                        <div style='font-size: 0.8rem; color: rgba(248, 250, 252, 0.6); text-transform: uppercase; font-weight: 500;'>Resolution Rate</div>
                        <div style='font-size: 2rem; font-weight: 700; color: #3B82F6; margin-top: 0.4rem;'>{analytics["resolution_rate"]}%</div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
            with col4:
                st.markdown(
                    f"""
                    <div style='background: rgba(255, 255, 255, 0.05); padding: 1.2rem; border-radius: 16px; border: 1px solid rgba(255, 255, 255, 0.08); text-align: center;'>
                        <div style='font-size: 0.8rem; color: rgba(248, 250, 252, 0.6); text-transform: uppercase; font-weight: 500;'>Escalations</div>
                        <div style='font-size: 2rem; font-weight: 700; color: #EF4444; margin-top: 0.4rem;'>{analytics["escalations"]}</div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )

            st.markdown("<br/>", unsafe_allow_html=True)
            st.markdown("### 📈 Sentiment Trend (Positive Score)")
            
            # Render sentiment trend line chart
            trend_df = pd.DataFrame(analytics["sentiment_trend"])
            trend_df.set_index("day", inplace=True)
            st.line_chart(trend_df["score"])
            
    except Exception as e:
        st.error(f"Failed to load analytics: {str(e)}")
    finally:
        db.close()

    st.markdown("<br/>", unsafe_allow_html=True)
    st.markdown(
        """
        <div style='text-align: center; margin-top: 1rem;'>
            <div style='background-color: rgba(15, 23, 42, 0.4); padding: 1.5rem; border-radius: 12px; border: 1px solid rgba(255, 255, 255, 0.05); display: inline-block;'>
                <h4 style='margin: 0; color: #10B981; font-weight: 600;'>🍔 Restaurant Tools Coming Soon</h4>
                <p style='margin: 8px 0 0 0; color: rgba(248, 250, 252, 0.5); font-size: 0.85rem;'>
                    Profile settings, RAG knowledge bases, and restaurant analytics tools are under preparation.
                </p>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )
