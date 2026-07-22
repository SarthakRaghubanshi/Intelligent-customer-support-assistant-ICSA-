import streamlit as st
import pandas as pd
from backend.database.database import get_db
from backend.services.analytics_service import AnalyticsService
from backend.services.knowledge_service import KnowledgeService
from backend.repositories.restaurant_repository import RestaurantRepository
from utils.icons import icon, chip

def render_admin_dashboard():
    """
    Renders the admin dashboard with global aggregates, single tenant insights,
    comparative analytics, and restaurant knowledge base views.
    """
    user = st.session_state.get("user", {})
    first = user.get("first_name") or ""
    last = user.get("last_name") or ""
    display_name = f"{first} {last}".strip() or user.get("email", "System Administrator")
    role_name = user.get("role", "admin")

    # Header — icon-chip hero
    st.markdown(
        f'''<div class="icsa-hero" style="display:flex;align-items:center;gap:16px;">
            {chip('admin', 24, 54, bg='var(--chip-accent)', color='var(--accent)', radius=15)}
            <div>
                <div class="icsa-eyebrow">Admin Console</div>
                <h2 style="margin:.15rem 0 0;">Welcome, {display_name}</h2>
                <p style="color:var(--muted);font-size:.9rem;margin:.25rem 0 0;">Platform-wide analytics, restaurants, and users.</p>
            </div>
        </div>''', unsafe_allow_html=True)
    st.markdown("<div style='height:1rem;'></div>", unsafe_allow_html=True)
    st.markdown(f'<div class="icsa-sec">{chip("insights", 18, 34)}<div class="t">Platform analytics</div><div class="d">Management control panel</div></div>', unsafe_allow_html=True)

    db_gen = get_db()
    db = next(db_gen)
    try:
        token = st.session_state.get("access_token")

        # Analysis scope selectbox including new Knowledge Base inspection scope
        scope = st.selectbox(
            "Select Analysis Scope:",
            options=["Global Overview", "Single Restaurant Detail", "Compare Restaurants", "Restaurant Knowledge Base", "Users & Restaurants", "Escalations", "Audit Log"]
        )

        st.markdown("<hr style='border-top: 1px solid var(--line);'/>", unsafe_allow_html=True)

        if scope == "Global Overview":
            analytics = AnalyticsService.get_global_analytics(db, token)
            
            # Metrics cards grid
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.markdown(
                    f'<div class="stat-tile accent"><div class="lab">{icon("insights",13)} Global tickets</div><div class="val">{analytics["total_tickets"]}</div></div>',
                    unsafe_allow_html=True
                )
            with col2:
                st.markdown(
                    f'<div class="stat-tile accent"><div class="lab">{icon("star",13)} Avg CSAT score</div><div class="val">{analytics["csat"]} / 5</div></div>',
                    unsafe_allow_html=True
                )
            with col3:
                st.markdown(
                    f'<div class="stat-tile accent"><div class="lab">{icon("resolved",13)} Avg resolution</div><div class="val">{analytics["resolution_rate"]}%</div></div>',
                    unsafe_allow_html=True
                )
            with col4:
                st.markdown(
                    f'<div class="stat-tile accent"><div class="lab">{icon("escalation",13)} Total escalations</div><div class="val">{analytics["escalations"]}</div></div>',
                    unsafe_allow_html=True
                )

            st.markdown("<div style='height:1rem;'></div>", unsafe_allow_html=True)
            st.markdown(f'<div class="icsa-sec">{chip("insights", 18, 34)}<div class="t">Aggregated sentiment trend</div><div class="d">Daily average</div></div>', unsafe_allow_html=True)
            trend_df = pd.DataFrame(analytics["sentiment_trend"])
            trend_df.set_index("day", inplace=True)
            st.line_chart(trend_df["score"], color="#7C74FF")

            st.markdown("<div style='height:1rem;'></div>", unsafe_allow_html=True)
            col_rt, col_intents = st.columns([1, 2])
            with col_rt:
                avg_ms = analytics.get("avg_response_time_ms", 0) or 0
                st.markdown(
                    f'<div class="stat-tile accent"><div class="lab">{icon("clock",13)} Avg response time</div><div class="val">{avg_ms / 1000:.2f}s</div></div>',
                    unsafe_allow_html=True
                )
            with col_intents:
                st.markdown(f'<div class="icsa-sec">{chip("insights", 18, 34)}<div class="t">Top intents</div></div>', unsafe_allow_html=True)
                top_intents = analytics.get("top_intents") or []
                if not top_intents:
                    st.caption("Top intents are available in the Single Restaurant Detail view.")
                else:
                    intents_df = pd.DataFrame(top_intents)
                    intents_df.columns = ["Intent", "Count"]
                    st.dataframe(intents_df, hide_index=True, use_container_width=True)

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
                        f'<div class="stat-tile accent"><div class="lab">{icon("insights",13)} Total tickets</div><div class="val">{analytics["total_tickets"]}</div></div>',
                        unsafe_allow_html=True
                    )
                with col2:
                    st.markdown(
                        f'<div class="stat-tile accent"><div class="lab">{icon("star",13)} CSAT score</div><div class="val">{analytics["csat"]} / 5</div></div>',
                        unsafe_allow_html=True
                    )
                with col3:
                    st.markdown(
                        f'<div class="stat-tile accent"><div class="lab">{icon("resolved",13)} Resolution rate</div><div class="val">{analytics["resolution_rate"]}%</div></div>',
                        unsafe_allow_html=True
                    )
                with col4:
                    st.markdown(
                        f'<div class="stat-tile accent"><div class="lab">{icon("escalation",13)} Escalations</div><div class="val">{analytics["escalations"]}</div></div>',
                        unsafe_allow_html=True
                    )

                st.markdown("<div style='height:1rem;'></div>", unsafe_allow_html=True)
                st.markdown(f'<div class="icsa-sec">{chip("insights", 18, 34)}<div class="t">Sentiment trend for {selected_name}</div></div>', unsafe_allow_html=True)
                trend_df = pd.DataFrame(analytics["sentiment_trend"])
                trend_df.set_index("day", inplace=True)
                st.line_chart(trend_df["score"], color="#7C74FF")

                st.markdown("<div style='height:1rem;'></div>", unsafe_allow_html=True)
                col_rt, col_intents = st.columns([1, 2])
                with col_rt:
                    avg_ms = analytics.get("avg_response_time_ms", 0) or 0
                    st.markdown(
                        f'<div class="stat-tile accent"><div class="lab">{icon("clock",13)} Avg response time</div><div class="val">{avg_ms / 1000:.2f}s</div></div>',
                        unsafe_allow_html=True
                    )
                with col_intents:
                    st.markdown(f'<div class="icsa-sec">{chip("insights", 18, 34)}<div class="t">Top intents</div></div>', unsafe_allow_html=True)
                    top_intents = analytics.get("top_intents") or []
                    if not top_intents:
                        st.caption("No intent data recorded yet.")
                    else:
                        intents_df = pd.DataFrame(top_intents)
                        intents_df.columns = ["Intent", "Count"]
                        st.dataframe(intents_df, hide_index=True, use_container_width=True)

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
                    st.warning("Please select at least two restaurants to view comparison metrics.")
                else:
                    selected_ids = [rest_map[name] for name in selected_names]
                    comparison_data = AnalyticsService.compare_restaurant_analytics(db, token, selected_ids)

                    # Construct and display comparative styled Markdown table
                    st.markdown(f'<div class="icsa-sec">{chip("insights", 18, 34)}<div class="t">Comparative analysis</div></div>', unsafe_allow_html=True)
                    
                    table_rows = []
                    table_rows.append("| Restaurant Name | Total Tickets | CSAT Score | Resolution Rate | Escalations |")
                    table_rows.append("| :--- | :---: | :---: | :---: | :---: |")
                    
                    for r_id, stats in comparison_data.items():
                        table_rows.append(
                            f"| **{stats['restaurant_name']}** | {stats['total_tickets']} | {stats['csat']} / 5 | {stats['resolution_rate']}% | {stats['escalations']} |"
                        )
                        
                    st.markdown("\n".join(table_rows), unsafe_allow_html=True)

        elif scope == "Restaurant Knowledge Base":
            st.markdown(f'<div class="icsa-sec">{chip("knowledge", 18, 34)}<div class="t">Knowledge base inspection</div></div>', unsafe_allow_html=True)
            active_rests = RestaurantRepository.list_active(db)
            if not active_rests:
                st.info("No active restaurants found on the platform.")
            else:
                rest_map = {r.name: r.id for r in active_rests}
                
                # Reuses active sidebar selected_restaurant context if matching name is found
                default_idx = 0
                sidebar_selected = st.session_state.get("selected_restaurant")
                for i, r in enumerate(active_rests):
                    if r.id == sidebar_selected or r.name == sidebar_selected:
                        default_idx = i
                        break
                        
                selected_name = st.selectbox("Select Restaurant:", options=list(rest_map.keys()), index=default_idx)
                selected_id = rest_map[selected_name]

                # Document search input
                search_query = st.text_input("Search documents by title:", placeholder="Type a title query to search...")

                # Retrieve matching documents using the service layer
                if search_query.strip():
                    docs = KnowledgeService.search_documents(db, token, selected_id, search_query)
                else:
                    docs = KnowledgeService.list_documents(db, token, selected_id)

                st.markdown("<div style='height:1rem;'></div>", unsafe_allow_html=True)
                doc_count = KnowledgeService.get_document_count(db, token, selected_id)
                st.info(f"Active documents in knowledge base: **{doc_count}**")

                if not docs:
                    st.write("No matching documents found in this restaurant's knowledge base.")
                else:
                    st.markdown("#### Document Results")
                    for doc in docs:
                        with st.expander(f"{doc.title} ({doc.document_type.upper()})"):
                            st.write(f"**Document ID:** `{doc.id}`")
                            st.write(f"**Created At:** {doc.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
                            st.write(f"**Last Updated:** {doc.updated_at.strftime('%Y-%m-%d %H:%M:%S')}")
                            st.markdown("---")
                            st.write("**Content Details:**")
                            st.info(doc.content)

        elif scope == "Users & Restaurants":
            st.markdown(f'<div class="icsa-sec">{chip("users", 18, 34)}<div class="t">Users & restaurants</div></div>', unsafe_allow_html=True)
            from backend.models.user import User

            restaurants = RestaurantRepository.list_active(db)
            users = db.query(User).filter(User.deleted_at.is_(None)).all()

            # Summary metric cards
            col_u, col_r = st.columns(2)
            with col_u:
                st.markdown(
                    f'<div class="stat-tile accent"><div class="lab">{icon("users",13)} Total users</div><div class="val">{len(users)}</div></div>',
                    unsafe_allow_html=True
                )
            with col_r:
                st.markdown(
                    f'<div class="stat-tile accent"><div class="lab">{icon("dashboard",13)} Active restaurants</div><div class="val">{len(restaurants)}</div></div>',
                    unsafe_allow_html=True
                )

            st.markdown("<div style='height:1rem;'></div>", unsafe_allow_html=True)
            st.markdown(f'<div class="icsa-sec">{chip("dashboard", 18, 34)}<div class="t">Restaurants</div></div>', unsafe_allow_html=True)
            if not restaurants:
                st.info("No active restaurants found on the platform.")
            else:
                rest_df = pd.DataFrame([
                    {
                        "Name": r.name,
                        "Phone": r.phone or "—",
                        "ID": r.id,
                        "Delivery Available": "Yes" if r.delivery_available else "No",
                    }
                    for r in restaurants
                ])
                st.dataframe(rest_df, hide_index=True, use_container_width=True)

            st.markdown("<div style='height:1rem;'></div>", unsafe_allow_html=True)
            st.markdown(f'<div class="icsa-sec">{chip("user", 18, 34)}<div class="t">Users</div></div>', unsafe_allow_html=True)
            if not users:
                st.info("No users found on the platform.")
            else:
                users_df = pd.DataFrame([
                    {
                        "Email": u.email,
                        "Role": u.role.value if u.role else "—",
                        "Name": f"{u.first_name or ''} {u.last_name or ''}".strip() or "—",
                        "Restaurant ID": u.restaurant_id or "—",
                    }
                    for u in users
                ])
                st.dataframe(users_df, hide_index=True, use_container_width=True)

        elif scope == "Escalations":
            st.markdown(f'<div class="icsa-sec">{chip("escalation", 18, 34)}<div class="t">Escalations</div><div class="d">Cross-tenant review (read-only)</div></div>', unsafe_allow_html=True)
            from backend.services.escalation_service import EscalationService
            from backend.models.user import User, UserRole

            admin_user = User(
                id=user.get("id"),
                email=user.get("email"),
                role=UserRole(user.get("role")),
                restaurant_id=user.get("restaurant_id")
            )

            try:
                escalations = EscalationService.get_escalations_for_restaurant(db, admin_user)
            except Exception as ee:
                st.error(f"Failed to load escalations: {str(ee)}")
                escalations = []

            rest_name_map = {r.id: r.name for r in RestaurantRepository.list_active(db)}
            status_pill_map = {"pending": "warn", "claimed": "muted", "resolved": "success"}
            prio_pill_map = {"high": "danger", "medium": "warn", "low": "muted"}

            if not escalations:
                st.info("No escalations found across the platform.")
            else:
                st.caption(f"{len(escalations)} escalation(s) across all restaurants.")
                for esc in escalations:
                    try:
                        rid = esc.conversation.restaurant_id if esc.conversation else None
                    except Exception:
                        rid = None
                    rname = rest_name_map.get(rid, "Unknown restaurant")
                    status_pill = status_pill_map.get(esc.status, "muted")
                    prio_pill = prio_pill_map.get(esc.priority, "muted")
                    created_str = esc.created_at.strftime('%Y-%m-%d %H:%M:%S') if esc.created_at else "N/A"

                    with st.expander(f"{rname} — {esc.reason} — {esc.status.upper()}"):
                        st.markdown(
                            f"""
                            <div style='display:flex;gap:8px;align-items:center;margin-bottom:10px;'>
                                <span class='pill {status_pill}'>{esc.status.upper()}</span>
                                <span class='pill {prio_pill}'>PRIORITY: {esc.priority.upper()}</span>
                                <span style='color:var(--muted);font-size:0.8rem;'>Created: {created_str}</span>
                            </div>
                            """,
                            unsafe_allow_html=True
                        )
                        st.markdown(f'<div class="icsa-sec">{chip("chat", 16, 30)}<div class="t">Conversation transcript</div></div>', unsafe_allow_html=True)
                        try:
                            messages = EscalationService.get_transcript(db, esc.id, admin_user)
                            if not messages:
                                st.caption("No messages in this conversation.")
                            for msg in messages:
                                st.markdown(f"**{msg.role.capitalize()}:** {msg.content}")
                        except Exception as te:
                            st.error(f"Failed to load transcript: {str(te)}")

        elif scope == "Audit Log":
            st.markdown(f'<div class="icsa-sec">{chip("settings", 18, 34)}<div class="t">Audit log</div><div class="d">Security & accountability trail</div></div>', unsafe_allow_html=True)
            from backend.services.audit_service import AuditService

            try:
                audit_rows = AuditService.list_recent(db, limit=100)
            except Exception as ae:
                st.error(f"Failed to load audit log: {str(ae)}")
                audit_rows = []

            if not audit_rows:
                st.info("No audit entries recorded yet.")
            else:
                st.caption(f"Showing {len(audit_rows)} most recent audit entries.")
                audit_df = pd.DataFrame([
                    {
                        "Time": r.created_at.strftime('%Y-%m-%d %H:%M:%S') if r.created_at else "—",
                        "Action": r.action,
                        "Actor": r.actor_email or "—",
                        "Entity": r.entity_type or "—",
                        "Entity ID": (r.entity_id[:8] if r.entity_id else "—"),
                        "Detail": r.detail or "—",
                    }
                    for r in audit_rows
                ])
                st.dataframe(audit_df, hide_index=True, use_container_width=True)

    except Exception as e:
        st.error(f"Failed to load dashboard data: {str(e)}")
    finally:
        db.close()

    st.markdown("<div style='height:1rem;'></div>", unsafe_allow_html=True)
    st.markdown(
        """
        <div class='icsa-card' style='text-align: center; margin-top: 1rem;'>
            <h4 style='margin: 0; color: var(--ink); font-weight: 600;'>Platform Administration Active</h4>
            <p style='margin: 8px 0 0 0; color: var(--muted); font-size: 0.85rem;'>
                Global analytics, per-tenant insights, comparative reporting, and user & restaurant management are live.
            </p>
        </div>
        """,
        unsafe_allow_html=True
    )
