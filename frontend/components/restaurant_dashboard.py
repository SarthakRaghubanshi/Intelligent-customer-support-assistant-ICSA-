import streamlit as st
import pandas as pd
from backend.database.database import get_db
from backend.services.analytics_service import AnalyticsService
from backend.services.knowledge_service import KnowledgeService
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
    tab_insights, tab_kb = st.tabs(["📊 Performance Insights", "📚 Knowledge Base"])

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
            
    except Exception as e:
        st.error(f"Failed to load dashboard data: {str(e)}")
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
