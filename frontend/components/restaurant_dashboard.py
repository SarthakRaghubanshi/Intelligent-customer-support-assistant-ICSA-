import streamlit as st
import pandas as pd
import io
import time
from backend.database.database import get_db
from backend.services.analytics_service import AnalyticsService
from backend.services.knowledge_service import KnowledgeService
from backend.services.restaurant_service import RestaurantService
from backend.core.document_types import DOCUMENT_TYPES
from utils.icons import icon, chip

def render_restaurant_dashboard():
    """
    Renders the restaurant dashboard with performance insights and knowledge base management.
    """
    user = st.session_state.get("user", {})
    first = user.get("first_name") or ""
    last = user.get("last_name") or ""
    display_name = f"{first} {last}".strip() or user.get("email", "Restaurant Manager")
    role_name = user.get("role", "restaurant")

    # App Branding using the icon-chip hero
    st.markdown(
        f'''<div class="icsa-hero" style="display:flex;align-items:center;gap:16px;">
            {chip('dashboard', 24, 54, bg='var(--chip-accent)', color='var(--accent)', radius=15)}
            <div>
                <div class="icsa-eyebrow">Restaurant Console</div>
                <h2 style="margin:.15rem 0 0;">Welcome, {display_name}</h2>
                <p style="color:var(--muted);font-size:.9rem;margin:.25rem 0 0;">Manage your menu, knowledge base, escalations, and performance.</p>
            </div>
        </div>''', unsafe_allow_html=True)
    st.markdown("<div style='height:1rem;'></div>", unsafe_allow_html=True)

    # Tabs layout for separation of concerns
    tab_insights, tab_kb, tab_conversations, tab_faqs, tab_profile, tab_escalations, tab_menu, tab_ai, tab_orders = st.tabs([
        "Performance Insights",
        "Knowledge Base",
        "Conversations",
        "FAQs",
        "Restaurant Profile",
        "Review Center",
        "Menu",
        "AI Settings",
        "Orders"
    ])

    db_gen = get_db()
    db = next(db_gen)
    try:
        restaurant_id = user.get("restaurant_id")
        token = st.session_state.get("access_token")

        if not restaurant_id:
            st.warning("No Restaurant Tenant assigned to this account.")
        else:
            # ==========================================
            # TAB 1: PERFORMANCE INSIGHTS
            # ==========================================
            with tab_insights:
                st.markdown(f'<div class="icsa-sec">{chip("insights", 18, 34)}<div class="t">Performance analytics</div></div>', unsafe_allow_html=True)
                analytics = AnalyticsService.get_restaurant_analytics(db, token, restaurant_id)

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
                st.markdown(f'<div class="icsa-sec">{chip("insights", 18, 34)}<div class="t">Sentiment trend</div><div class="d">Positive score</div></div>', unsafe_allow_html=True)

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

            # ==========================================
            # TAB 2: KNOWLEDGE BASE
            # ==========================================
            with tab_kb:
                st.markdown(f'<div class="icsa-sec">{chip("knowledge", 18, 34)}<div class="t">Knowledge base</div></div>', unsafe_allow_html=True)

                # Retrieve documents count and items using the service layer
                doc_count = KnowledgeService.get_document_count(db, token, restaurant_id)
                st.info(f"Active documents in knowledge base: **{doc_count}**")

                docs = KnowledgeService.list_documents(db, token, restaurant_id)

                # --- SECTION: UPLOAD & INGEST KNOWLEDGE DOCUMENT ---
                if "uploaded_doc_preview" in st.session_state:
                    preview_data = st.session_state["uploaded_doc_preview"]
                    with st.expander(f"Parsed Document Preview: {preview_data['title']}", expanded=True):
                        st.info("Showing first 500 characters of the parsed text.")
                        preview_text = preview_data['content'][:500] + ("..." if len(preview_data['content']) > 500 else "")
                        st.text_area("Preview (read-only):", value=preview_text, height=150, disabled=True)
                        if st.button("Clear Preview"):
                            del st.session_state["uploaded_doc_preview"]
                            st.rerun()

                with st.expander("Ingest New Knowledge Document (File Upload)"):
                    with st.form("upload_doc_form", clear_on_submit=True):
                        uploaded_file = st.file_uploader(
                            "Upload File (PDF, DOCX, CSV, TXT - Max 10MB):",
                            type=["pdf", "docx", "csv", "txt"]
                        )
                        upload_title = st.text_input("Document Title (optional, defaults to filename):", placeholder="e.g. Zone 1 Delivery Fees")
                        upload_type = st.selectbox("Document Type:", options=DOCUMENT_TYPES)
                        
                        submit_upload = st.form_submit_button("Ingest and Index Document")
                        if submit_upload:
                            if uploaded_file is None:
                                st.error("Please select a file to upload.")
                            else:
                                try:
                                    progress_bar = st.progress(0)
                                    status_text = st.empty()
                                    
                                    status_text.text("Validating size and extensions...")
                                    progress_bar.progress(30)
                                    time.sleep(0.2)
                                    
                                    final_title = upload_title.strip() or uploaded_file.name
                                    
                                    status_text.text("Parsing document content...")
                                    progress_bar.progress(60)
                                    time.sleep(0.2)
                                    
                                    # Read stream in-memory
                                    file_bytes = uploaded_file.read()
                                    file_stream = io.BytesIO(file_bytes)
                                    
                                    doc = KnowledgeService.upload_document_file(
                                        db=db,
                                        token=token,
                                        restaurant_id=restaurant_id,
                                        file_stream=file_stream,
                                        filename=uploaded_file.name,
                                        title=final_title,
                                        document_type=upload_type,
                                        reported_mime=uploaded_file.type
                                    )
                                    
                                    status_text.text("Indexing vectors in ChromaDB...")
                                    progress_bar.progress(90)
                                    time.sleep(0.2)
                                    
                                    progress_bar.progress(100)
                                    status_text.empty()
                                    
                                    # Save to session state for persistence across rerun
                                    st.session_state["uploaded_doc_preview"] = {
                                        "title": doc.title,
                                        "content": doc.content
                                    }
                                    
                                    st.success(f"Document '{doc.title}' successfully ingested and indexed!")
                                    time.sleep(1)
                                    st.rerun()
                                except Exception as err:
                                    st.error(f"Failed to ingest document: {str(err)}")

                st.markdown("<div style='height:1rem;'></div>", unsafe_allow_html=True)

                # --- SECTION: LIST & MANAGE EXISTING DOCUMENTS ---
                if not docs:
                    st.write("No documents found in your knowledge base. Add your first document above!")
                else:
                    st.markdown("#### Existing Documents")
                    for doc in docs:
                        with st.expander(f"{doc.title} ({doc.document_type.upper()})"):
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
                                    submit_save = st.form_submit_button("Save Changes")
                                with col_del:
                                    submit_delete = st.form_submit_button("Delete Document")

                                if submit_save:
                                    if not edit_title.strip() or not edit_content.strip():
                                        st.error("Title and Content cannot be empty.")
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
            # TAB: CONVERSATIONS (review ALL AI conversations)
            # ==========================================
            with tab_conversations:
                from backend.services.conversation_service import ConversationService
                st.markdown(f'<div class="icsa-sec">{chip("chat", 18, 34)}<div class="t">Conversations</div><div class="d">Review all AI conversations</div></div>', unsafe_allow_html=True)

                try:
                    convs = ConversationService.list_for_restaurant(db, token, restaurant_id, limit=100)
                except Exception as cerr:
                    st.error(f"Failed to load conversations: {str(cerr)}")
                    convs = []

                conv_status_pill = {"active": "muted", "escalated": "warn", "resolved": "success"}

                if not convs:
                    st.info("No conversations recorded yet.")
                else:
                    st.caption(f"Showing {len(convs)} most recent conversations.")
                    conv_options = {}
                    for c in convs:
                        created_str = c.created_at.strftime('%Y-%m-%d %H:%M') if c.created_at else "N/A"
                        pill = conv_status_pill.get(c.status, "muted")
                        st.markdown(
                            f"""
                            <div class='icsa-card' style='margin-bottom:0.5rem;display:flex;justify-content:space-between;align-items:center;'>
                                <span style='font-weight:600;color:var(--ink);'>#{c.id[:8]}</span>
                                <span style='display:flex;gap:10px;align-items:center;'>
                                    <span class='pill {pill}'>{c.status.upper()}</span>
                                    <span style='color:var(--muted);font-size:0.8rem;'>{created_str}</span>
                                </span>
                            </div>
                            """,
                            unsafe_allow_html=True
                        )
                        conv_options[f"#{c.id[:8]} · {c.status.upper()} · {created_str}"] = c

                    st.markdown("<div style='height:0.75rem;'></div>", unsafe_allow_html=True)
                    selected_conv_label = st.selectbox(
                        "View transcript for conversation:",
                        options=list(conv_options.keys()),
                        key="conv_transcript_select"
                    )
                    selected_conv = conv_options[selected_conv_label]

                    st.markdown(f'<div class="icsa-sec">{chip("chat", 16, 30)}<div class="t">Transcript</div><div class="d">#{selected_conv.id[:8]}</div></div>', unsafe_allow_html=True)
                    try:
                        transcript = ConversationService.get_transcript(db, token, selected_conv.id)
                        if not transcript:
                            st.caption("No messages in this conversation yet.")
                        for msg in transcript:
                            is_user = msg.role == "user"
                            who = "Customer" if is_user else msg.role.capitalize()
                            role_pill = "accent" if is_user else "success"
                            meta_bits = []
                            if getattr(msg, "intent", None):
                                meta_bits.append(f"<span class='pill muted'>intent: {msg.intent}</span>")
                            if getattr(msg, "sentiment", None):
                                meta_bits.append(f"<span class='pill muted'>sentiment: {msg.sentiment}</span>")
                            ts_str = msg.timestamp.strftime('%Y-%m-%d %H:%M') if getattr(msg, "timestamp", None) else ""
                            meta_html = " ".join(meta_bits)
                            st.markdown(
                                f"""
                                <div class='icsa-card' style='margin-bottom:0.5rem;'>
                                    <div style='display:flex;justify-content:space-between;align-items:center;margin-bottom:0.35rem;'>
                                        <span class='pill {role_pill}'>{who}</span>
                                        <span style='color:var(--muted);font-size:0.75rem;'>{ts_str}</span>
                                    </div>
                                    <div style='color:var(--ink);font-size:0.9rem;'>{msg.content}</div>
                                    <div style='margin-top:0.4rem;display:flex;gap:6px;'>{meta_html}</div>
                                </div>
                                """,
                                unsafe_allow_html=True
                            )
                    except Exception as terr:
                        st.error(f"Failed to load transcript: {str(terr)}")

            # ==========================================
            # TAB: FAQS (train curated instant answers)
            # ==========================================
            with tab_faqs:
                from backend.services.faq_service import FaqService
                st.markdown(f'<div class="icsa-sec">{chip("knowledge", 18, 34)}<div class="t">Train a FAQ</div><div class="d">Curated instant answers</div></div>', unsafe_allow_html=True)

                with st.form("add_faq_form", clear_on_submit=True):
                    faq_question = st.text_input("Question", key="faq_q_input", placeholder="e.g. Do you offer vegan options?")
                    faq_answer = st.text_area("Answer", key="faq_a_input", placeholder="e.g. Yes, we have a dedicated vegan menu.")
                    submit_faq = st.form_submit_button("Add FAQ")
                    if submit_faq:
                        if not faq_question.strip() or not faq_answer.strip():
                            st.error("Both a question and an answer are required.")
                        else:
                            try:
                                FaqService.add_faq(db, token, restaurant_id, faq_question, faq_answer)
                                st.success("FAQ added! It is answerable immediately.")
                                st.rerun()
                            except Exception as ferr:
                                st.error(f"Failed to add FAQ: {str(ferr)}")

                st.markdown("<div style='height:0.75rem;'></div>", unsafe_allow_html=True)
                try:
                    faqs = FaqService.list_faqs(db, restaurant_id)
                except Exception as ferr:
                    st.error(f"Failed to load FAQs: {str(ferr)}")
                    faqs = []

                with st.expander(f"Current FAQs ({len(faqs)})", expanded=bool(faqs)):
                    if not faqs:
                        st.caption("No curated FAQs yet. Add your first one above.")
                    else:
                        for q, a in faqs:
                            st.markdown(f"**Q:** {q}")
                            st.markdown(f"**A:** {a}")
                            st.markdown("<hr style='border-top:1px solid var(--line);margin:0.5rem 0;'/>", unsafe_allow_html=True)

            # ==========================================
            # TAB 3: RESTAURANT PROFILE
            # ==========================================
            with tab_profile:
                st.markdown(f'<div class="icsa-sec">{chip("profile", 18, 34)}<div class="t">Restaurant profile</div></div>', unsafe_allow_html=True)
                try:
                    profile = RestaurantService.get_profile(db, token, restaurant_id)
                    
                    # Verify editing capabilities
                    can_edit = (role_name == "restaurant" or role_name == "admin")
                    disabled = not can_edit
                    
                    if disabled:
                        st.info("Profile fields are read-only for customer roles.")

                    with st.form(f"edit_profile_form_{restaurant_id}"):
                        prof_name = st.text_input("Restaurant Name:", value=profile.name, disabled=disabled)
                        prof_desc = st.text_area("Description:", value=profile.description or "", disabled=disabled)
                        prof_phone = st.text_input("Phone Number:", value=profile.phone or "", disabled=disabled)
                        prof_address = st.text_input("Address:", value=profile.address or "", disabled=disabled)
                        prof_email = st.text_input("Contact Email:", value=profile.contact_email or "", disabled=disabled)
                        prof_status = st.text_input("Status Message:", value=profile.status_message or "", placeholder="e.g. Open Today", disabled=disabled)
                        
                        st.markdown("---")
                        st.markdown("#### Delivery Settings")
                        prof_delivery_avail = st.checkbox("Delivery Available?", value=profile.delivery_available, disabled=disabled)
                        prof_delivery_notes = st.text_area("Delivery Notes / Instructions:", value=profile.delivery_notes or "", disabled=disabled)
                        
                        st.markdown("---")
                        st.markdown("#### Operational Business Hours")
                        
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

                        st.markdown("<div style='height:1rem;'></div>", unsafe_allow_html=True)
                        submit_profile = st.form_submit_button("Save Profile Changes", disabled=disabled)
                        
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
                st.markdown(f'<div class="icsa-sec">{chip("escalation", 18, 34)}<div class="t">Review center</div><div class="d">Escalation board</div></div>', unsafe_allow_html=True)
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
                    status_pill = {
                        "pending": "warn",
                        "claimed": "muted",
                        "resolved": "success",
                    }.get(esc.status, "muted")
                    prio_pill = {
                        "high": "danger",
                        "medium": "warn",
                        "low": "muted",
                    }.get(esc.priority, "muted")

                    header_str = f"Ticket: {esc.reason} | Status: {esc.status.upper()} | Priority: {esc.priority.upper()}"

                    with st.expander(header_str):
                        created_str = esc.created_at.strftime('%Y-%m-%d %H:%M:%S') if esc.created_at else 'N/A'
                        st.markdown(
                            f"""
                            <div style='display: flex; gap: 8px; align-items: center; margin-bottom: 10px;'>
                                <span class='pill {status_pill}'>{esc.status.upper()}</span>
                                <span class='pill {prio_pill}'>PRIORITY: {esc.priority.upper()}</span>
                                <span style='color: var(--muted); font-size: 0.8rem;'>Created: {created_str}</span>
                            </div>
                            """,
                            unsafe_allow_html=True
                        )

                        # Show Transcript
                        st.markdown(f'<div class="icsa-sec">{chip("chat", 16, 30)}<div class="t">Conversation transcript</div></div>', unsafe_allow_html=True)
                        try:
                            messages = EscalationService.get_transcript(db, esc.id, user_obj)
                            for msg in messages:
                                st.markdown(f"**{msg.role.capitalize()}:** {msg.content}")
                        except Exception as te:
                            st.error(f"Failed to load transcript: {str(te)}")

                        # Add Notes section
                        st.markdown("---")
                        st.markdown("#### Internal Notes")
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
                            if st.button("Claim Escalation", key=f"claim_{esc.id}", use_container_width=True):
                                try:
                                    EscalationService.claim_escalation(db, esc.id, user_obj)
                                    st.success("Case successfully claimed!")
                                    st.rerun()
                                except Exception as ce:
                                    st.error(f"Failed to claim: {str(ce)}")
                        elif esc.status == "claimed":
                            if esc.assigned_to == user_obj.id:
                                st.markdown("#### Resolve Case")
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

            # ==========================================
            # TAB 5: MENU MANAGEMENT
            # ==========================================
            with tab_menu:
                st.markdown(f'<div class="icsa-sec">{chip("menu", 18, 34)}<div class="t">Menu management</div></div>', unsafe_allow_html=True)
                from backend.services.menu_service import MenuService
                from backend.repositories.product_repository import ProductRepository

                # --- SECTION: ADD MENU ITEM ---
                with st.expander("Add menu item"):
                    with st.form("add_menu_item_form", clear_on_submit=True):
                        new_name = st.text_input("Name:", key="menu_new_name", placeholder="e.g. Margherita Pizza")
                        new_category = st.text_input("Category:", key="menu_new_category", placeholder="e.g. Pizza")
                        new_price = st.number_input("Base Price (₹):", min_value=0.0, step=1.0, key="menu_new_price")
                        new_desc = st.text_area("Description:", key="menu_new_desc")
                        new_tags = st.multiselect(
                            "Dietary tags:",
                            options=["vegetarian", "vegan", "non-vegetarian", "gluten-free"],
                            key="menu_new_tags"
                        )
                        new_popular = st.checkbox("Mark as popular", key="menu_new_popular")
                        submit_menu = st.form_submit_button("Add Item")
                        if submit_menu:
                            if not new_name.strip() or not new_category.strip():
                                st.error("Name and Category are required.")
                            else:
                                try:
                                    ProductRepository.create(
                                        db,
                                        restaurant_id=restaurant_id,
                                        name=new_name,
                                        category=new_category,
                                        base_price=new_price,
                                        description=new_desc,
                                        dietary_tags=new_tags,
                                        is_popular=new_popular
                                    )
                                    st.success(f"Menu item '{new_name}' added!")
                                    st.rerun()
                                except Exception as merr:
                                    st.error(f"Failed to add menu item: {str(merr)}")

                st.markdown("<div style='height:1rem;'></div>", unsafe_allow_html=True)

                # --- SECTION: LIST MENU GROUPED BY CATEGORY ---
                products = MenuService.list_products(db, restaurant_id, only_available=False)
                if not products:
                    st.info("No menu items yet. Add your first item above!")
                else:
                    grouped = {}
                    for p in products:
                        grouped.setdefault(p["category"] or "Uncategorized", []).append(p)

                    for category in sorted(grouped.keys()):
                        st.markdown(f"#### {category}")
                        for p in grouped[category]:
                            if p.get("size_prices"):
                                price_str = " / ".join(f"{k}: ₹{v}" for k, v in p["size_prices"].items())
                            else:
                                price_str = f"₹{p['base_price']:.0f}"
                            tags = ", ".join(p.get("dietary_tags") or []) or "—"
                            popular_marker = f" <span class='pill accent' style='margin-left:6px;'>{icon('star', 11)}popular</span>" if p.get("is_popular") else ""
                            avail_marker = "" if p.get("is_available") else " <span class='pill muted' style='margin-left:6px;'>unavailable</span>"
                            st.markdown(
                                f"""
                                <div class='icsa-card' style='margin-bottom: 0.6rem;'>
                                    <div style='display: flex; justify-content: space-between; align-items: center;'>
                                        <span style='font-weight: 600; color: var(--ink);'>{p['name']}{popular_marker}{avail_marker}</span>
                                        <span style='color: var(--accent-deep); font-weight: 700;'>{price_str}</span>
                                    </div>
                                    <div style='color: var(--muted); font-size: 0.8rem; margin-top: 0.3rem;'>Dietary: {tags}</div>
                                </div>
                                """,
                                unsafe_allow_html=True
                            )

            # ==========================================
            # TAB 6: AI SETTINGS
            # ==========================================
            with tab_ai:
                st.markdown(f'<div class="icsa-sec">{chip("ai", 18, 34)}<div class="t">AI assistant settings</div></div>', unsafe_allow_html=True)
                st.caption(
                    "When the AI Assistant is disabled, the chatbot stops answering "
                    "customer questions and tells customers that a staff member will "
                    "follow up with them shortly."
                )
                try:
                    cfg = RestaurantService.get_ai_config(db, restaurant_id)
                    with st.form("ai_config_form"):
                        ai_enabled = st.toggle(
                            "AI Assistant Enabled",
                            value=bool(cfg.get("ai_enabled", True)),
                            key="ai_cfg_enabled"
                        )
                        greeting = st.text_area(
                            "Greeting message",
                            value=cfg.get("greeting", "") or "",
                            key="ai_cfg_greeting"
                        )
                        threshold = st.slider(
                            "Low-confidence escalation threshold",
                            min_value=0.0,
                            max_value=1.0,
                            value=float(cfg.get("low_confidence_threshold", 0.6)),
                            step=0.05,
                            key="ai_cfg_threshold",
                            help="If the assistant's confidence falls below this value, the conversation is escalated to a human."
                        )

                        st.markdown("<hr style='border-top:1px solid var(--line);'/>", unsafe_allow_html=True)
                        st.markdown(f'<div class="icsa-sec">{chip("escalation", 16, 30)}<div class="t">Escalation rules</div><div class="d">Which triggers hand off to a human</div></div>', unsafe_allow_html=True)
                        current_rules = cfg.get("enabled_rules", {}) or {}
                        rule_defs = [
                            ("refund", "Refund requests"),
                            ("complaint", "Complaints"),
                            ("abuse", "Abusive language"),
                            ("human", "Human-agent requests"),
                            ("negative", "Negative sentiment"),
                            ("low_confidence", "Low AI confidence"),
                        ]
                        rule_cols = st.columns(2)
                        new_rules = {}
                        for r_idx, (r_key, r_label) in enumerate(rule_defs):
                            with rule_cols[r_idx % 2]:
                                new_rules[r_key] = st.checkbox(
                                    r_label,
                                    value=bool(current_rules.get(r_key, True)),
                                    key=f"ai_cfg_rule_{r_key}"
                                )
                        st.caption("Disabled rules stop triggering escalation.")

                        submit_ai = st.form_submit_button("Save AI Settings")
                        if submit_ai:
                            try:
                                RestaurantService.update_ai_config(
                                    db, token, restaurant_id,
                                    {
                                        "ai_enabled": ai_enabled,
                                        "greeting": greeting,
                                        "low_confidence_threshold": threshold,
                                        "enabled_rules": new_rules
                                    }
                                )
                                st.success("AI settings saved!")
                            except Exception as aerr:
                                st.error(f"Failed to save AI settings: {str(aerr)}")
                except Exception as aerr:
                    st.error(f"Failed to load AI settings: {str(aerr)}")

            # ==========================================
            # TAB 7: ORDERS
            # ==========================================
            with tab_orders:
                st.markdown(f'<div class="icsa-sec">{chip("orders", 18, 34)}<div class="t">Recent orders</div></div>', unsafe_allow_html=True)
                from backend.repositories.order_repository import OrderRepository
                from backend.models.order import ORDER_STATUSES

                orders = OrderRepository.list_by_restaurant(db, restaurant_id, limit=50)
                if not orders:
                    st.info("No orders found for this restaurant yet.")
                else:
                    status_pill_map = {
                        "placed": "muted",
                        "confirmed": "accent",
                        "preparing": "warn",
                        "ready": "accent",
                        "out_for_delivery": "accent",
                        "delivered": "success",
                        "completed": "success",
                        "cancelled": "danger",
                    }
                    for order in orders:
                        status_pill = status_pill_map.get(order.status, "muted")
                        items_summary = ", ".join(
                            f"{it.quantity}× {it.product_name}" + (f" ({it.size})" if it.size else "")
                            for it in order.items
                        ) or "No items"
                        placed_str = order.placed_at.strftime('%Y-%m-%d %H:%M') if order.placed_at else "N/A"
                        with st.expander(f"Order {order.order_number} — {order.status.upper()} — ₹{order.total:.0f}"):
                            st.markdown(
                                f"""
                                <div style='display: flex; gap: 8px; align-items: center; margin-bottom: 10px;'>
                                    <span class='pill {status_pill}'>{order.status.upper()}</span>
                                    <span style='color: var(--muted); font-size: 0.8rem;'>{order.order_type.capitalize()} · Placed {placed_str}</span>
                                </div>
                                """,
                                unsafe_allow_html=True
                            )
                            st.markdown(f"**Items:** {items_summary}")
                            st.markdown(f"**Total:** ₹{order.total:.2f}")

                            current_idx = ORDER_STATUSES.index(order.status) if order.status in ORDER_STATUSES else 0
                            new_status = st.selectbox(
                                "Update status:",
                                options=ORDER_STATUSES,
                                index=current_idx,
                                key=f"status_{order.id}"
                            )
                            if st.button("Update Status", key=f"status_btn_{order.id}"):
                                try:
                                    OrderRepository.update_status(db, order.id, new_status)
                                    st.success(f"Order {order.order_number} updated to {new_status}.")
                                    st.rerun()
                                except Exception as oerr:
                                    st.error(f"Failed to update order: {str(oerr)}")
    except Exception as e:
        st.error(f"Failed to load dashboard data: {str(e)}")
    finally:
        db.close()

    st.markdown("<div style='height:1rem;'></div>", unsafe_allow_html=True)
    st.markdown(
        """
        <div class='icsa-card' style='text-align: center; margin-top: 1rem;'>
            <h4 style='margin: 0; color: var(--ink); font-weight: 600;'>Restaurant Tools Active</h4>
            <p style='margin: 8px 0 0 0; color: var(--muted); font-size: 0.85rem;'>
                Profile settings, RAG knowledge bases, and restaurant analytics tools are ready for customer support workflows.
            </p>
        </div>
        """,
        unsafe_allow_html=True
    )
