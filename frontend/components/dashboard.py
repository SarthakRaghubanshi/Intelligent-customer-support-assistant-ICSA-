import streamlit as st
import textwrap
import pandas as pd
from backend.analytics.session_analytics import get_session_analytics, get_all_tenant_analytics

def render_dashboard():
    """Renders the operations and customer support analytics dashboard with business insights."""
    # Retrieve current session statistics
    selected = st.session_state.selected_restaurant
    if selected == "All Restaurants":
        stats = get_session_analytics(None)
    else:
        stats = get_session_analytics(selected)
    total = stats.get("total_queries", 0)
    recent_events = stats.get("recent_events", [])

    # Calculate Fallback Rate
    fallback_count = stats.get("fallback_count", 0)
    fallback_rate = (fallback_count / total) if total > 0 else 0.0

    st.markdown(
        textwrap.dedent(
            """
            <div style='display: flex; align-items: center; gap: 16px; margin-bottom: 2rem;'>
                <div style='background: linear-gradient(135deg, #10B981, #059669); padding: 12px; border-radius: 14px; display: inline-flex; box-shadow: 0 4px 15px rgba(16, 185, 129, 0.3);'>
                    <span style='font-size: 1.6rem; color: white;'>📊</span>
                </div>
                <div>
                    <h2 style='margin: 0; font-size: 1.8rem; font-weight: 600; color: #F8FAFC;'>Operations & Support Analytics</h2>
                    <p style='margin: 0; font-size: 0.85rem; color: rgba(248, 250, 252, 0.5); font-weight: 300;'>
                        Real-time KPIs, response metrics, query frequencies, and automated business insights.
                    </p>
                </div>
            </div>
            """
        ),
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

    # 2. Secondary Metrics Row (5 columns)
    st.markdown("### 📋 Secondary Operational Metrics")
    s_col1, s_col2, s_col3, s_col4, s_col5 = st.columns(5)
    with s_col1:
        st.metric(label="Avg Similarity Score", value=f"{stats.get('average_similarity_score', 0.0):.4f}")
    with s_col2:
        st.metric(label="Avg Confidence Score", value=f"{stats.get('average_confidence_score', 0.0):.4f}")
    with s_col3:
        st.metric(label="Gemini Responses", value=stats.get("gemini_count", 0))
    with s_col4:
        st.metric(label="Fallback Responses", value=fallback_count)
    with s_col5:
        st.metric(label="Escalation Count", value=stats.get("escalation_count", 0))

    st.markdown("<hr style='border: 0; border-top: 1px solid rgba(255, 255, 255, 0.05); margin: 2rem 0;'/>", unsafe_allow_html=True)

    # 3. Business Insights Section
    st.markdown("### 💡 Business Insights & Observations")
    if total > 0:
        # Calculate top intent
        intent_dist = stats.get("intent_distribution", {})
        top_intent = max(intent_dist, key=intent_dist.get) if intent_dist else "None"
        
        # Calculate top language
        lang_dist = stats.get("language_distribution", {})
        top_lang = max(lang_dist, key=lang_dist.get) if lang_dist else "None"
        
        # Calculate escalation percent
        esc_pct = stats.get("escalation_rate", 0.0) * 100
        
        # Fallback alert indicator
        if fallback_rate > 0.20:
            fallback_status = f"<span style='color: #F59E0B;'>⚠️ <strong>High Fallback Rate ({fallback_rate * 100:.1f}%)</strong></span>: A significant portion of queries did not match the knowledge base. Consider expanding your RAG documents context."
        else:
            fallback_status = f"<span style='color: #10B981;'>🟢 <strong>Healthy Fallback Rate ({fallback_rate * 100:.1f}%)</strong></span>: RAG system coverage is matching customer queries efficiently."
            
        # Complaint alert indicator
        complaint_count = 0
        for ev in recent_events:
            if ev.get("intent") == "Complaint" or ev.get("escalation_reason") == "Customer Complaint":
                complaint_count += 1
                
        if complaint_count > 0:
            complaint_status = f"<span style='color: #EF4444;'>⚠️ <strong>Support Action Required</strong></span>: {complaint_count} customer complaint(s) filed in this session. Review the complaints below and contact affected customers."
        else:
            complaint_status = "<span style='color: #10B981;'>🟢 <strong>Perfect Service Quality</strong></span>: No customer complaints have been filed so far in this session."
            
        insights_html = f"""
        <div style='background-color: rgba(30, 41, 59, 0.4); padding: 1.5rem; border-radius: 12px; border: 1px solid rgba(255, 255, 255, 0.05); line-height: 1.6;'>
            <ul style='margin: 0; padding-left: 20px; color: #F8FAFC;'>
                <li style='margin-bottom: 8px;'>🔥 <strong>Most Common Customer Intent:</strong> <span style='color: #6C5CE7; font-weight: bold;'>{top_intent}</span></li>
                <li style='margin-bottom: 8px;'>🌐 <strong>Most Common Language:</strong> <span style='color: #10B981; font-weight: bold;'>{top_lang}</span></li>
                <li style='margin-bottom: 8px;'>🛎️ <strong>Escalated Conversations:</strong> <span style='color: #F59E0B; font-weight: bold;'>{esc_pct:.1f}%</span> of all support turns.</li>
                <li style='margin-bottom: 8px;'>🤖 <strong>RAG System Health:</strong> {fallback_status}</li>
                <li>📋 <strong>Service Quality Status:</strong> {complaint_status}</li>
            </ul>
        </div>
        """
        st.markdown(textwrap.dedent(insights_html), unsafe_allow_html=True)
    else:
        st.info("Awaiting traffic to generate business insights and session metrics.")

    st.markdown("<hr style='border: 0; border-top: 1px solid rgba(255, 255, 255, 0.05); margin: 2rem 0;'/>", unsafe_allow_html=True)

    # 3.5. Tenant Comparison Section (Visible only when 'All Restaurants' is selected)
    if selected == "All Restaurants":
        st.markdown("### 🏢 Admin Tenant Comparison")
        all_tenant_stats = get_all_tenant_analytics()
        if all_tenant_stats:
            comparison_rows = []
            volume_data = {}
            escalation_data = {}
            
            # Sort tenants by name to ensure consistent UI rendering
            for tenant_id in sorted(all_tenant_stats.keys()):
                t_stats = all_tenant_stats[tenant_id]
                comparison_rows.append({
                    "Tenant": tenant_id,
                    "Total Queries": t_stats.get("total_queries", 0),
                    "Escalation Rate": f"{t_stats.get('escalation_rate', 0.0) * 100:.1f}%",
                    "Avg Latency (ms)": f"{t_stats.get('average_latency_ms', 0.0):.1f}",
                    "Avg Confidence": f"{t_stats.get('average_confidence_score', 0.0):.4f}",
                    "Avg Similarity": f"{t_stats.get('average_similarity_score', 0.0):.4f}"
                })
                volume_data[tenant_id] = t_stats.get("total_queries", 0)
                escalation_data[tenant_id] = t_stats.get("escalation_count", 0)
            
            df_comparison = pd.DataFrame(comparison_rows)
            st.dataframe(df_comparison, use_container_width=True, hide_index=True)
            
            comp_col1, comp_col2 = st.columns(2)
            with comp_col1:
                st.markdown("#### Query Volume by Tenant")
                st.bar_chart(pd.Series(volume_data))
            with comp_col2:
                st.markdown("#### Escalation Count by Tenant")
                st.bar_chart(pd.Series(escalation_data))
        else:
            st.info("No active tenant analytics available yet for comparison.")
            
        st.markdown("<hr style='border: 0; border-top: 1px solid rgba(255, 255, 255, 0.05); margin: 2rem 0;'/>", unsafe_allow_html=True)

    # 4. Most Common Questions and Complaints Section (2 columns)
    st.markdown("### 🔍 Frequency Analysis & Report")
    freq_col1, freq_col2 = st.columns(2)
    
    with freq_col1:
        st.markdown("#### 🔹 Most Common Questions")
        # Extract query frequency
        query_freq = {}
        for ev in recent_events:
            q = ev.get("query", "").strip()
            if q:
                query_freq[q] = query_freq.get(q, 0) + 1
        top_queries = sorted(query_freq.items(), key=lambda x: x[1], reverse=True)[:5]
        
        if top_queries:
            for q, count in top_queries:
                st.markdown(f"❓ **\"{q}\"** : `{count} calls`", unsafe_allow_html=True)
        else:
            st.info("No queries recorded yet.")

    with freq_col2:
        st.markdown("#### ⚠️ Most Common Complaints")
        # Extract complaint frequency
        complaint_freq = {}
        for ev in recent_events:
            if ev.get("intent") == "Complaint" or ev.get("escalation_reason") == "Customer Complaint":
                q = ev.get("query", "").strip()
                if q:
                    complaint_freq[q] = complaint_freq.get(q, 0) + 1
        top_complaints = sorted(complaint_freq.items(), key=lambda x: x[1], reverse=True)[:5]
        
        if top_complaints:
            for q, count in top_complaints:
                st.markdown(f"💔 **\"{q}\"** : `{count} complaints`", unsafe_allow_html=True)
        else:
            st.info("No customer complaints recorded in this session.")

    st.markdown("<hr style='border: 0; border-top: 1px solid rgba(255, 255, 255, 0.05); margin: 2rem 0;'/>", unsafe_allow_html=True)

    # 5. Recent Analytics Activity Table
    st.markdown("### 📋 Recent Analytics Activity Log")
    if recent_events:
        table_html = (
            "<div style='overflow-x: auto;'>\n"
            "<table style='width: 100%; border-collapse: collapse; font-size: 0.9rem;'>\n"
            "    <thead>\n"
            "        <tr style='border-bottom: 2px solid rgba(255, 255, 255, 0.1); text-align: left;'>\n"
            "            <th style='padding: 10px; color: rgba(248, 250, 252, 0.6);'>Time</th>\n"
            "            <th style='padding: 10px; color: rgba(248, 250, 252, 0.6);'>Query</th>\n"
            "            <th style='padding: 10px; color: rgba(248, 250, 252, 0.6);'>Intent (Confidence)</th>\n"
            "            <th style='padding: 10px; color: rgba(248, 250, 252, 0.6);'>Sentiment</th>\n"
            "            <th style='padding: 10px; color: rgba(248, 250, 252, 0.6);'>Latency</th>\n"
            "            <th style='padding: 10px; color: rgba(248, 250, 252, 0.6);'>Escalated</th>\n"
            "        </tr>\n"
            "    </thead>\n"
            "    <tbody>\n"
        )
        for ev in reversed(recent_events[-5:]):
            ts = ev.get("timestamp", "")
            if ts and "T" in ts:
                ts = ts.split("T")[1][:8]
            esc_str = "<span style='color: #EF4444; font-weight: bold;'>Yes ⚠️</span>" if ev.get("escalated") else "No"
            table_html += (
                f"        <tr style='border-bottom: 1px solid rgba(255, 255, 255, 0.05);'>\n"
                f"            <td style='padding: 10px; font-weight: 500;'>{ts}</td>\n"
                f"            <td style='padding: 10px;'>{ev.get('query', '')}</td>\n"
                f"            <td style='padding: 10px;'>{ev.get('intent', '')} ({ev.get('intent_confidence', 0.0):.2f})</td>\n"
                f"            <td style='padding: 10px;'>{ev.get('sentiment', '')}</td>\n"
                f"            <td style='padding: 10px;'>{ev.get('latency_ms', 0.0):.1f} ms</td>\n"
                f"            <td style='padding: 10px;'>{esc_str}</td>\n"
                f"        </tr>\n"
            )
        table_html += "    </tbody>\n</table>\n</div>"
        st.markdown(table_html, unsafe_allow_html=True)
    else:
        st.info("No activity logged yet in this session.")

    st.markdown("<hr style='border: 0; border-top: 1px solid rgba(255, 255, 255, 0.05); margin: 2rem 0;'/>", unsafe_allow_html=True)

    # 6. Distribution Charts (2 rows of 2 columns)
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

    st.markdown("<hr style='border: 0; border-top: 1px solid rgba(255, 255, 255, 0.05); margin: 2rem 0;'/>", unsafe_allow_html=True)

    # 7. Trend Graphs Section
    st.markdown("### 📈 Performance & Sentiment Trends Over Time")
    if recent_events:
        df = pd.DataFrame(recent_events)
        df['Time'] = pd.to_datetime(df['timestamp']).dt.strftime('%H:%M:%S')

        trend_col1, trend_col2 = st.columns(2)
        with trend_col1:
            st.markdown("#### Query Volume & Escalation Trend")
            volume_df = pd.DataFrame({
                'Time': df['Time'],
                'Total Queries': range(1, len(df) + 1),
                'Escalations': df['escalated'].astype(int).cumsum()
            }).set_index('Time')
            st.line_chart(volume_df)

            st.markdown("#### Sentiment Score Trend")
            sentiment_map = {'Positive': 1, 'Neutral': 0, 'Negative': -1}
            sentiment_df = pd.DataFrame({
                'Time': df['Time'],
                'Sentiment Score': df['sentiment'].map(sentiment_map).fillna(0)
            }).set_index('Time')
            st.line_chart(sentiment_df)

        with trend_col2:
            st.markdown("#### Intent Confidence Trend")
            confidence_df = df[['Time', 'intent_confidence']].rename(
                columns={'intent_confidence': 'Confidence Score'}
            ).set_index('Time')
            st.line_chart(confidence_df)

            # Extra info block for portfolio completeness
            st.markdown(
                textwrap.dedent(
                    """
                    <div style='background-color: rgba(30, 41, 59, 0.2); padding: 1.2rem; border-radius: 10px; border: 1px solid rgba(255, 255, 255, 0.03); margin-top: 1.5rem;'>
                        <h5 style='margin-top: 0; color: #F8FAFC;'>💡 Time-Series Analysis</h5>
                        <p style='font-size: 0.8rem; color: rgba(248, 250, 252, 0.6); line-height: 1.5; margin: 0;'>
                            These trend charts illustrate support performance and client sentiment patterns chronologically. 
                            Use the <strong>Sentiment Score Trend</strong> to map immediate customer satisfaction changes (ranging from 1 to -1). 
                            Observe the <strong>Confidence Trend</strong> to detect vocabulary coverage drift.
                        </p>
                    </div>
                    """
                ),
                unsafe_allow_html=True
            )
    else:
        st.info("Awaiting traffic to generate trend charts.")
