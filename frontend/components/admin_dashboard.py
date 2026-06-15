import streamlit as st
import pandas as pd
from backend.database.database import get_db
from backend.services.analytics_service import AnalyticsService
from backend.repositories.restaurant_repository import RestaurantRepository

def render_admin_dashboard():
    """
    Renders the admin dashboard with global aggregates, single tenant insights,
    and comparative analytics tools.
    """
    user = st.session_state.get("user", {})
    first = user.get("first_name") or ""
    last = user.get("last_name") or ""
    display_name = f"{first} {last}".strip() or user.get("email", "System Administrator")
    role_name = user.get("role", "admin")

    # Header Card
    st.markdown(
        f"""
        <div style='background: linear-gradient(135deg, rgba(239, 68, 68, 0.1), rgba(108, 92, 231, 0.15)); padding: 2.5rem; border-radius: 20px; border: 1px solid rgba(239, 68, 68, 0.25); text-align: center; margin-top: 2rem; box-shadow: 0 8px 32px rgba(0, 0, 0, 0.15);'>
            <div style='font-size: 3.5rem; margin-bottom: 1rem;'>⚙️</div>
            <h2 style='margin: 0; font-size: 2rem; font-weight: 700; color: #F8FAFC;'>Welcome, {display_name}!</h2>
            <p style='color: rgba(248, 250, 252, 0.6); font-size: 1rem; margin-top: 0.5rem; font-weight: 300;'>
                Account Role: <span style='background-color: #EF4444; color: white; padding: 2px 8px; border-radius: 12px; font-size: 0.8rem; font-weight: 600; text-transform: uppercase;'>{role_name}</span>
            </p>
        </div>
        """,
        unsafe_allow_html=True
    )

    st.markdown("<br/>", unsafe_allow_html=True)
    st.markdown("### 📊 Platform Analytics Control Panel")

    db_gen = get_db()
    db = next(db_gen)
    try:
        token = st.session_state.get("access_token")

        # Analysis scope selectbox
        scope = st.selectbox(
            "Select Analysis Scope:",
            options=["Global Overview", "Single Restaurant Detail", "Compare Restaurants"]
        )

        st.markdown("<hr style='border-top: 1px solid rgba(255, 255, 255, 0.05);'/>", unsafe_allow_html=True)

        if scope == "Global Overview":
            analytics = AnalyticsService.get_global_analytics(db, token)
            
            # Metrics cards grid
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.markdown(
                    f"""
                    <div style='background: rgba(255, 255, 255, 0.05); padding: 1.2rem; border-radius: 16px; border: 1px solid rgba(255, 255, 255, 0.08); text-align: center;'>
                        <div style='font-size: 0.8rem; color: rgba(248, 250, 252, 0.6); text-transform: uppercase; font-weight: 500;'>Global Tickets</div>
                        <div style='font-size: 2rem; font-weight: 700; color: #6C5CE7; margin-top: 0.4rem;'>{analytics["total_tickets"]}</div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
            with col2:
                st.markdown(
                    f"""
                    <div style='background: rgba(255, 255, 255, 0.05); padding: 1.2rem; border-radius: 16px; border: 1px solid rgba(255, 255, 255, 0.08); text-align: center;'>
                        <div style='font-size: 0.8rem; color: rgba(248, 250, 252, 0.6); text-transform: uppercase; font-weight: 500;'>Avg CSAT Score</div>
                        <div style='font-size: 2rem; font-weight: 700; color: #10B981; margin-top: 0.4rem;'>{analytics["csat"]} / 5</div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
            with col3:
                st.markdown(
                    f"""
                    <div style='background: rgba(255, 255, 255, 0.05); padding: 1.2rem; border-radius: 16px; border: 1px solid rgba(255, 255, 255, 0.08); text-align: center;'>
                        <div style='font-size: 0.8rem; color: rgba(248, 250, 252, 0.6); text-transform: uppercase; font-weight: 500;'>Avg Resolution</div>
                        <div style='font-size: 2rem; font-weight: 700; color: #3B82F6; margin-top: 0.4rem;'>{analytics["resolution_rate"]}%</div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
            with col4:
                st.markdown(
                    f"""
                    <div style='background: rgba(255, 255, 255, 0.05); padding: 1.2rem; border-radius: 16px; border: 1px solid rgba(255, 255, 255, 0.08); text-align: center;'>
                        <div style='font-size: 0.8rem; color: rgba(248, 250, 252, 0.6); text-transform: uppercase; font-weight: 500;'>Total Escalations</div>
                        <div style='font-size: 2rem; font-weight: 700; color: #EF4444; margin-top: 0.4rem;'>{analytics["escalations"]}</div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )

            st.markdown("<br/>", unsafe_allow_html=True)
            st.markdown("### 📈 Aggregated Sentiment Trend (Daily Average)")
            trend_df = pd.DataFrame(analytics["sentiment_trend"])
            trend_df.set_index("day", inplace=True)
            st.line_chart(trend_df["score"])

        elif scope == "Single Restaurant Detail":
            active_rests = RestaurantRepository.list_active(db)
            if not active_rests:
                st.info("No active restaurants found on the platform.")
            else:
                rest_map = {r.name: r.id for r in active_rests}
                selected_name = st.selectbox("Select Restaurant:", options=list(rest_map.keys()))
                selected_id = rest_map[selected_name]

                analytics = AnalyticsService.get_restaurant_analytics(db, token, selected_id)

                # Metrics cards grid
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
                st.markdown(f"### 📈 Sentiment Trend for {selected_name}")
                trend_df = pd.DataFrame(analytics["sentiment_trend"])
                trend_df.set_index("day", inplace=True)
                st.line_chart(trend_df["score"])

        elif scope == "Compare Restaurants":
            active_rests = RestaurantRepository.list_active(db)
            if len(active_rests) < 2:
                st.info("At least two active restaurants must exist on the platform to run comparisons.")
            else:
                rest_map = {r.name: r.id for r in active_rests}
                selected_names = st.multiselect(
                    "Select Restaurants to Compare:",
                    options=list(rest_map.keys()),
                    default=list(rest_map.keys())[:2]
                )

                if len(selected_names) < 2:
                    st.warning("⚠️ Please select at least two restaurants to view comparison metrics.")
                else:
                    selected_ids = [rest_map[name] for name in selected_names]
                    comparison_data = AnalyticsService.compare_restaurant_analytics(db, token, selected_ids)
                    
                    # Construct and display comparative styled Markdown table
                    st.markdown("### 📊 Comparative Analysis Table")
                    
                    table_rows = []
                    table_rows.append("| Restaurant Name | Total Tickets | CSAT Score | Resolution Rate | Escalations |")
                    table_rows.append("| :--- | :---: | :---: | :---: | :---: |")
                    
                    for r_id, stats in comparison_data.items():
                        table_rows.append(
                            f"| **{stats['restaurant_name']}** | {stats['total_tickets']} | {stats['csat']} / 5 | {stats['resolution_rate']}% | {stats['escalations']} |"
                        )
                        
                    st.markdown("\n".join(table_rows), unsafe_allow_html=True)
                    
    except Exception as e:
        st.error(f"Failed to load analytics: {str(e)}")
    finally:
        db.close()

    st.markdown("<br/>", unsafe_allow_html=True)
    st.markdown(
        """
        <div style='text-align: center; margin-top: 1rem;'>
            <div style='background-color: rgba(15, 23, 42, 0.4); padding: 1.5rem; border-radius: 12px; border: 1px solid rgba(255, 255, 255, 0.05); display: inline-block;'>
                <h4 style='margin: 0; color: #EF4444; font-weight: 600;'>🛠️ System Administration Coming Soon</h4>
                <p style='margin: 8px 0 0 0; color: rgba(248, 250, 252, 0.5); font-size: 0.85rem;'>
                    Multi-tenant management panels, global configurations, and analytics logs are under preparation.
                </p>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )
