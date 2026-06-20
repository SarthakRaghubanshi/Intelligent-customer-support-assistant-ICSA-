import streamlit as st
import pandas as pd
from backend.database.database import get_db
from backend.services.analytics_service import AnalyticsService
from backend.services.knowledge_service import KnowledgeService
from backend.services.restaurant_service import RestaurantService
from backend.core.document_types import DOCUMENT_TYPES

def render_restaurant_dashboard():
    """
    Renders the restaurant dashboard with performance insights and knowledge base management.
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

    # Tabs layout for separation of concerns
    tab_insights, tab_kb, tab_profile, tab_escalations = st.tabs([
        "📊 Performance Insights",
        "📚 Knowledge Base",
        "🏪 Restaurant Profile",
        "🚨 Review Center & Escalation Board"
    ])

    db_gen = get_db()
    db = next(db_gen)
    try:
        restaurant_id = user.get("restaurant_id")
        token = st.session_state.get("access_token")

        if not restaurant_id:
            st.warning("⚠️ No Restaurant Tenant assigned to this account.")
        else:
            # ==========================================
            # TAB 1: PERFORMANCE INSIGHTS
            # ==========================================
            with tab_insights:
                st.markdown("### 📊 Business Performance Analytics")
                analytics = AnalyticsService.get_restaurant_analytics(db, token, restaurant_id)
                
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
                
                trend_df = pd.DataFrame(analytics["sentiment_trend"])
                trend_df.set_index("day", inplace=True)
                st.line_chart(trend_df["score"])

            # ==========================================
            # TAB 2: KNOWLEDGE BASE
            # ==========================================
            with tab_kb:
                st.markdown("### 📚 Restaurant Knowledge Base Management")
                
                # Retrieve documents count and items using the service layer
                doc_count = KnowledgeService.get_document_count(db, token, restaurant_id)
                st.info(f"ℹ️ Active Documents in Knowledge Base: **{doc_count}**")
                
                docs = KnowledgeService.list_documents(db, token, restaurant_id)
                
                # --- SECTION: CREATE NEW DOCUMENT ---
                with st.expander("➕ Create New Knowledge Document"):
                    with st.form("create_doc_form", clear_on_submit=True):
                        new_title = st.text_input("Document Title:", placeholder="e.g. Zone 1 Delivery Fees")
                        new_type = st.selectbox("Document Type:", options=DOCUMENT_TYPES)
                        new_content = st.text_area("Document Content:", placeholder="Write or paste your knowledge document text here...")
                        
                        submit_create = st.form_submit_button("Save Document")
                        if submit_create:
                            if not new_title.strip() or not new_content.strip():
                                st.error("⚠️ Title and Content are required fields.")
                            else:
                                try:
                                    KnowledgeService.create_document(
                                        db=db,
                                        token=token,
                                        restaurant_id=restaurant_id,
                                        title=new_title,
                                        content=new_content,
                                        document_type=new_type
                                    )
                                    st.success(f"✓ Document '{new_title}' successfully created!")
                                    st.rerun()
                                except Exception as err:
                                    st.error(f"Failed to create document: {str(err)}")

                st.markdown("<br/>", unsafe_allow_html=True)
                
                # --- SECTION: LIST & MANAGE EXISTING DOCUMENTS ---
                if not docs:
                    st.write("No documents found in your knowledge base. Add your first document above!")
                else:
                    st.markdown("#### Existing Documents")
                    for doc in docs:
                        with st.expander(f"📄 {doc.title} ({doc.document_type.upper()})"):
                            # Render formatted details
                            st.write(f"**ID:** `{doc.id}`")
                            st.write(f"**Last Updated:** {doc.updated_at.strftime('%Y-%m-%d %H:%M:%S')}")
                            
                            # Edit Form
                            with st.form(f"edit_doc_form_{doc.id}"):
                                edit_title = st.text_input("Edit Title:", value=doc.title)
                                edit_type = st.selectbox("Edit Type:", options=DOCUMENT_TYPES, index=DOCUMENT_TYPES.index(doc.document_type) if doc.document_type in DOCUMENT_TYPES else 0)
                                edit_content = st.text_area("Edit Content:", value=doc.content, height=150)
                                
                                col_save, col_del = st.columns([1, 1])
                                with col_save:
                                    submit_save = st.form_submit_button("💾 Save Changes")
                                with col_del:
                                    submit_delete = st.form_submit_button("🗑️ Delete Document")

                                if submit_save:
                                    if not edit_title.strip() or not edit_content.strip():
                                        st.error("⚠️ Title and Content cannot be empty.")
                                    else:
                                        try:
                                            KnowledgeService.update_document(
                                                db=db,
                                                token=token,
                                                doc_id=doc.id,
                                                update_dict={
                                                    "title": edit_title,
                                                    "document_type": edit_type,
                                                    "content": edit_content
                                                }
                                            )
                                            st.success("✓ Changes saved!")
                                            st.rerun()
                                        except Exception as err:
                                            st.error(f"Failed to save changes: {str(err)}")

                                if submit_delete:
                                    try:
                                        KnowledgeService.delete_document(db, token, doc.id)
                                        st.success("✓ Document successfully deleted!")
                                        st.rerun()
                                    except Exception as err:
                                        st.error(f"Failed to delete document: {str(err)}")
            # ==========================================
            # TAB 3: RESTAURANT PROFILE
            # ==========================================
            with tab_profile:
                st.markdown("### 🏪 Restaurant Profile Configuration")
                try:
                    profile = RestaurantService.get_profile(db, token, restaurant_id)
                    
                    # Verify editing capabilities
                    can_edit = (role_name == "restaurant" or role_name == "admin")
                    disabled = not can_edit
                    
                    if disabled:
                        st.info("ℹ️ Profile fields are read-only for customer roles.")

                    with st.form(f"edit_profile_form_{restaurant_id}"):
                        prof_name = st.text_input("Restaurant Name:", value=profile.name, disabled=disabled)
                        prof_desc = st.text_area("Description:", value=profile.description or "", disabled=disabled)
                        prof_phone = st.text_input("Phone Number:", value=profile.phone or "", disabled=disabled)
                        prof_address = st.text_input("Address:", value=profile.address or "", disabled=disabled)
                        prof_email = st.text_input("Contact Email:", value=profile.contact_email or "", disabled=disabled)
                        prof_status = st.text_input("Status Message:", value=profile.status_message or "", placeholder="e.g. Open Today", disabled=disabled)
                        
                        st.markdown("---")
                        st.markdown("#### 🚚 Delivery Settings")
                        prof_delivery_avail = st.checkbox("Delivery Available?", value=profile.delivery_available, disabled=disabled)
                        prof_delivery_notes = st.text_area("Delivery Notes / Instructions:", value=profile.delivery_notes or "", disabled=disabled)
                        
                        st.markdown("---")
                        st.markdown("#### 🕒 Operational Business Hours")
                        
                        hours_data = profile.business_hours or {}
                        days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
                        new_hours = {}
                        
                        for day in days:
                            day_record = hours_data.get(day) or {}
                            
                            col_day, col_open, col_close, col_closed = st.columns([1.5, 2.5, 2.5, 1.5])
                            with col_day:
                                st.markdown(f"<div style='margin-top: 25px; font-weight: bold;'>{day}</div>", unsafe_allow_html=True)
                            with col_closed:
                                day_closed = st.checkbox("Closed", value=day_record.get("closed", False), key=f"closed_{day}", disabled=disabled)
                            with col_open:
                                day_open = st.text_input("Open (HH:MM):", value=day_record.get("open") or "09:00", key=f"open_{day}", disabled=disabled or day_closed)
                            with col_close:
                                day_close = st.text_input("Close (HH:MM):", value=day_record.get("close") or "22:00", key=f"close_{day}", disabled=disabled or day_closed)
                            
                            new_hours[day] = {
                                "open": None if day_closed else day_open,
                                "close": None if day_closed else day_close,
                                "closed": day_closed
                            }

                        st.markdown("<br/>", unsafe_allow_html=True)
                        submit_profile = st.form_submit_button("💾 Save Profile Changes", disabled=disabled)
                        
                        if submit_profile:
                            try:
                                update_data = {
                                    "name": prof_name,
                                    "description": prof_desc,
                                    "phone": prof_phone,
                                    "address": prof_address,
                                    "contact_email": prof_email,
                                    "business_hours": new_hours,
                                    "delivery_available": prof_delivery_avail,
                                    "delivery_notes": prof_delivery_notes,
                                    "status_message": prof_status
                                }
                                RestaurantService.update_profile(db, token, restaurant_id, update_data)
                                st.success("✓ Restaurant Profile successfully updated!")
                                st.rerun()
                            except Exception as err:
                                st.error(f"Failed to update profile: {str(err)}")
                except Exception as err:
                    st.error(f"Failed to load profile details: {str(err)}")
            # ==========================================
            # TAB 4: REVIEW CENTER & ESCALATION BOARD
            # ==========================================
            with tab_escalations:
                st.markdown("### 🚨 Review Center & Escalation Board")
                from backend.services.escalation_service import EscalationService
                from backend.models.user import User, UserRole
                
                # Fetch escalations scoped by tenant/role
                user_obj = User(
                    id=user.get("id"),
                    email=user.get("email"),
                    role=UserRole(user.get("role")),
                    restaurant_id=restaurant_id
                )
                
                try:
                    escalations = EscalationService.get_escalations_for_restaurant(db, user_obj)
                except Exception as e:
                    st.error(f"Error fetching escalations: {str(e)}")
                    escalations = []
                
                # Filter Panel
                col_status, col_priority = st.columns(2)
                with col_status:
                    filter_status = st.selectbox(
                        "Filter by Status:",
                        options=["All", "pending", "claimed", "resolved"]
                    )
                with col_priority:
                    filter_priority = st.selectbox(
                        "Filter by Priority:",
                        options=["All", "high", "medium", "low"]
                    )
                
                # Filter items in memory
                filtered_escalations = escalations
                if filter_status != "All":
                    filtered_escalations = [e for e in filtered_escalations if e.status == filter_status]
                if filter_priority != "All":
                    filtered_escalations = [e for e in filtered_escalations if e.priority == filter_priority]
                
                if not filtered_escalations:
                    st.info("No escalations match the current filters.")
                
                for esc in filtered_escalations:
                    badge_colors = {
                        "pending": "#EF4444",   # red
                        "claimed": "#F59E0B",   # amber
                        "resolved": "#10B981"   # green
                    }
                    badge_color = badge_colors.get(esc.status, "#6B7280")
                    priority_colors = {
                        "high": "#EF4444",
                        "medium": "#F59E0B",
                        "low": "#6B7280"
                    }
                    prio_color = priority_colors.get(esc.priority, "#6B7280")
                    
                    header_str = f"Ticket: {esc.reason} | Status: {esc.status.upper()} | Priority: {esc.priority.upper()}"
                    
                    with st.expander(header_str):
                        st.markdown(
                            f"""
                            <div style='display: flex; gap: 10px; margin-bottom: 10px;'>
                                <span style='background-color: {badge_color}; color: white; padding: 2px 8px; border-radius: 12px; font-size: 0.75rem; font-weight: bold;'>{esc.status.upper()}</span>
                                <span style='background-color: {prio_color}; color: white; padding: 2px 8px; border-radius: 12px; font-size: 0.75rem; font-weight: bold;'>PRIORITY: {esc.priority.upper()}</span>
                                <span style='color: rgba(255,255,255,0.4); font-size: 0.8rem;'>Created: {esc.created_at.strftime('%Y-%m-%d %H:%M:%S') if esc.created_at else 'N/A'}</span>
                            </div>
                            """,
                            unsafe_allow_html=True
                        )
                        
                        # Show Transcript
                        st.markdown("#### 💬 Conversation Transcript")
                        try:
                            messages = EscalationService.get_transcript(db, esc.id, user_obj)
                            for msg in messages:
                                role_icon = "👤" if msg.role == "user" else "🤖"
                                st.markdown(f"**{role_icon} {msg.role.capitalize()}:** {msg.content}")
                        except Exception as te:
                            st.error(f"Failed to load transcript: {str(te)}")
                        
                        # Add Notes section
                        st.markdown("---")
                        st.markdown("#### 📝 Internal Notes")
                        current_notes = esc.notes or ""
                        note_input = st.text_area(f"Add/Edit notes for {esc.id[:8]}", value=current_notes, key=f"notes_{esc.id}")
                        if st.button("Save Notes", key=f"save_notes_btn_{esc.id}"):
                            try:
                                EscalationService.add_notes(db, esc.id, user_obj, note_input)
                                st.success("Notes saved successfully!")
                                st.rerun()
                            except Exception as ne:
                                st.error(f"Failed to save notes: {str(ne)}")
                                
                        # Claim / Resolve controls
                        if esc.status == "pending":
                            if st.button("🔒 Claim Escalation", key=f"claim_{esc.id}", use_container_width=True):
                                try:
                                    EscalationService.claim_escalation(db, esc.id, user_obj)
                                    st.success("Case successfully claimed!")
                                    st.rerun()
                                except Exception as ce:
                                    st.error(f"Failed to claim: {str(ce)}")
                        elif esc.status == "claimed":
                            if esc.assigned_to == user_obj.id:
                                st.markdown("#### ✅ Resolve Case")
                                res_summary = st.text_area("Resolution Summary:", placeholder="Provide details about how this case was resolved...", key=f"res_{esc.id}")
                                if st.button("Resolve case", key=f"resolve_btn_{esc.id}", use_container_width=True):
                                    if not res_summary.strip():
                                        st.error("Resolution summary cannot be empty.")
                                    else:
                                        try:
                                            EscalationService.resolve_escalation(db, esc.id, user_obj, res_summary)
                                            st.success("Case marked as resolved!")
                                            st.rerun()
                                        except Exception as re:
                                            st.error(f"Failed to resolve: {str(re)}")
                            else:
                                st.info(f"Assigned to manager with ID: {esc.assigned_to}")
                        elif esc.status == "resolved":
                            st.success(f"Resolved by agent ID: {esc.resolved_by} at {esc.resolved_at.strftime('%Y-%m-%d %H:%M:%S') if esc.resolved_at else 'N/A'}")
                            st.markdown(f"**Resolution Summary:** {esc.resolution_summary or 'None'}")
    except Exception as e:
        st.error(f"Failed to load dashboard data: {str(e)}")
    finally:
        db.close()

    st.markdown("<br/>", unsafe_allow_html=True)
    st.markdown(
        """
        <div style='text-align: center; margin-top: 1rem;'>
            <div style='background-color: rgba(15, 23, 42, 0.4); padding: 1.5rem; border-radius: 12px; border: 1px solid rgba(255, 255, 255, 0.05); display: inline-block;'>
                <h4 style='margin: 0; color: #10B981; font-weight: 600;'>🏪 Restaurant Tools Active</h4>
                <p style='margin: 8px 0 0 0; color: rgba(248, 250, 252, 0.5); font-size: 0.85rem;'>
                    Profile settings, RAG knowledge bases, and restaurant analytics tools are ready for customer support workflows.
                </p>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )
