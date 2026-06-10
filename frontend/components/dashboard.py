import streamlit as st
from backend.analytics.session_analytics import get_session_analytics

def render_dashboard():
    """Renders the operations and customer support analytics dashboard."""
    # Retrieve current session statistics
    stats = get_session_analytics()
    total = stats.get("total_queries", 0)

    # Calculate Fallback Rate
    fallback_count = stats.get("fallback_count", 0)
    fallback_rate = (fallback_count / total) if total > 0 else 0.0

    st.markdown(
        """
        <div style='display: flex; align-items: center; gap: 16px; margin-bottom: 2rem;'>
            <div style='background: linear-gradient(135deg, #10B981, #059669); padding: 12px; border-radius: 14px; display: inline-flex; box-shadow: 0 4px 15px rgba(16, 185, 129, 0.3);'>
                <span style='font-size: 1.6rem; color: white;'>📊</span>
            </div>
            <div>
                <h2 style='margin: 0; font-size: 1.8rem; font-weight: 600; color: #F8FAFC;'>Operations & Support Analytics</h2>
                <p style='margin: 0; font-size: 0.85rem; color: rgba(248, 250, 252, 0.5); font-weight: 300;'>
                    Real-time KPIs, response metrics, language distributions, and human escalation rates.
                </p>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    # 1. Primary KPIs Row (4 columns)
    st.markdown("### 📈 Primary Performance Indicators")
    p_col1, p_col2, p_col3, p_col4 = st.columns(4)
    with p_col1:
        st.metric(label="Total Queries", value=total)
    with p_col2:
        st.metric(label="Fallback Rate", value=f"{fallback_rate * 100:.1f}%")
    with p_col3:
        st.metric(label="Escalation Rate", value=f"{stats.get('escalation_rate', 0.0) * 100:.1f}%")
    with p_col4:
        st.metric(label="Average Latency", value=f"{stats.get('average_latency_ms', 0.0):.1f} ms")

    st.markdown("<hr style='border: 0; border-top: 1px solid rgba(255, 255, 255, 0.05); margin: 2rem 0;'/>", unsafe_allow_html=True)

    # 2. Secondary Metrics Row (4 columns)
    st.markdown("### 📋 Secondary Operational Metrics")
    s_col1, s_col2, s_col3, s_col4 = st.columns(4)
    with s_col1:
        st.metric(label="Avg Similarity Score", value=f"{stats.get('average_similarity_score', 0.0):.4f}")
    with s_col2:
        st.metric(label="Gemini Responses", value=stats.get("gemini_count", 0))
    with s_col3:
        st.metric(label="Fallback Responses", value=fallback_count)
    with s_col4:
        st.metric(label="Escalation Count", value=stats.get("escalation_count", 0))

    st.markdown("<hr style='border: 0; border-top: 1px solid rgba(255, 255, 255, 0.05); margin: 2rem 0;'/>", unsafe_allow_html=True)

    # 3. Distribution Charts (2 rows of 2 columns)
    st.markdown("### 📊 Distribution Breakdown")
    
    chart_row1_col1, chart_row1_col2 = st.columns(2)
    with chart_row1_col1:
        st.markdown("#### Intent Distribution")
        intent_dist = stats.get("intent_distribution", {})
        if intent_dist:
            st.bar_chart(intent_dist)
        else:
            st.info("No intent data recorded yet.")

    with chart_row1_col2:
        st.markdown("#### Sentiment Distribution")
        sentiment_dist = stats.get("sentiment_distribution", {})
        if sentiment_dist:
            st.bar_chart(sentiment_dist)
        else:
            st.info("No sentiment data recorded yet.")

    chart_row2_col1, chart_row2_col2 = st.columns(2)
    with chart_row2_col1:
        st.markdown("#### Language Distribution")
        language_dist = stats.get("language_distribution", {})
        if language_dist:
            st.bar_chart(language_dist)
        else:
            st.info("No language data recorded yet.")

    with chart_row2_col2:
        st.markdown("#### Escalation Reason Distribution")
        reason_dist = stats.get("escalation_reason_distribution", {})
        if reason_dist:
            st.bar_chart(reason_dist)
        else:
            st.info("No escalation reasons recorded yet.")
