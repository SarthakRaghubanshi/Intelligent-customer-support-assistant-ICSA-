import os
import sys
import shutil
from datetime import datetime
from unittest import mock

# 1. Resolve paths
current_file_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_file_dir)
if project_root not in sys.path:
    sys.path.append(project_root)
# frontend/ must be importable so `from utils.icons import ...` resolves the same
# way it does under `streamlit run frontend/app.py`.
_frontend_dir = os.path.join(project_root, "frontend")
if _frontend_dir not in sys.path:
    sys.path.insert(0, _frontend_dir)

# 2. Force an isolated test database
test_db_path = os.path.join(project_root, "data", "test_source_rendering.db")
os.environ["DATABASE_URL"] = f"sqlite:///{test_db_path}"

# Clean test db file if it already exists
if os.path.exists(test_db_path):
    try:
        os.remove(test_db_path)
    except Exception:
        pass

from tests.utils.test_bootstrap import bootstrap_test_database, bootstrap_restaurant
from backend.repositories.message_repository import MessageRepository
from backend.repositories.conversation_repository import ConversationRepository
from backend.repositories.user_repository import UserRepository
from backend.models.user import UserRole
from backend.models.message import Message

# Mock Streamlit session state wrapper
class MockSessionState(dict):
    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)
    def __setattr__(self, name, value):
        self[name] = value

mock_state = MockSessionState()
mock_state.user = {
    "id": "customer-user-123",
    "email": "customer@test.com",
    "first_name": "Test",
    "last_name": "User",
    "role": "customer"
}
mock_state.messages = []
mock_state.selected_restaurant = None
mock_state.current_chat_restaurant = None

# Mock streamlit functions
import streamlit as st
st.session_state = mock_state

# We mock all Streamlit functions that are called in render_customer_dashboard
mock_markdown = mock.MagicMock()
mock_selectbox = mock.MagicMock()
mock_chat_message = mock.MagicMock()
mock_chat_input = mock.MagicMock(return_value=None)
mock_columns = mock.MagicMock(return_value=[mock.MagicMock(), mock.MagicMock()])
mock_button = mock.MagicMock(return_value=False)
mock_slider = mock.MagicMock(return_value=5)
mock_text_area = mock.MagicMock(return_value="")
mock_success = mock.MagicMock()
mock_error = mock.MagicMock()
mock_rerun = mock.MagicMock()

# Setup expander context manager mock
mock_expander_ctx = mock.MagicMock()
mock_expander = mock.MagicMock(return_value=mock_expander_ctx)
mock_caption = mock.MagicMock()
mock_info = mock.MagicMock()

st.markdown = mock_markdown
st.selectbox = mock_selectbox
st.chat_message = mock_chat_message
st.chat_input = mock_chat_input
st.columns = mock_columns
st.button = mock_button
st.slider = mock_slider
st.text_area = mock_text_area
st.success = mock_success
st.error = mock_error
st.rerun = mock_rerun
st.expander = mock_expander
st.caption = mock_caption
st.info = mock_info

# Import the dashboard layout code to test
from frontend.components.customer_dashboard import render_customer_dashboard

def run_source_rendering_tests():
    print("=" * 80)
    print("RUNNING DEF-01 REMEDIATION CITATION RENDERING TESTS")
    print("=" * 80)

    # 1. Initialize test database
    print("\n1. Bootstrapping isolated test database...")
    SessionLocalTest = bootstrap_test_database(os.environ["DATABASE_URL"])
    db = SessionLocalTest()

    try:
        # Create test restaurant
        restaurant = bootstrap_restaurant(db, "rest-test-99", "Gourmet Pizza Place")
        
        # Create test customer user matching the session state id
        customer = UserRepository.create(
            db=db,
            email="customer@test.com",
            password_raw="password123",
            role=UserRole.CUSTOMER,
            first_name="Test",
            last_name="User"
        )
        # Ensure correct ID for session consistency
        customer.id = "customer-user-123"
        db.commit()

        # =====================================================================
        # TEST 1: Message persistence, storage, and reload loops
        # =====================================================================
        print("\n2. Testing Message persistence and source JSON storage...")
        conv = ConversationRepository.create(db, customer_id=customer.id, restaurant_id=restaurant.id)
        
        # Message with populated sources
        test_sources = [
            {
                "document_id": "doc-uuid-1",
                "title": "Refund Guide",
                "document_type": "refund_policy",
                "snippet": "Orders cancelled within 5 mins qualify for a refund."
            },
            {
                "document_id": "doc-uuid-2",
                "title": "Pizza Menu",
                "document_type": "menu",
                "snippet": "Margherita: tomato sauce, fresh mozzarella, basil."
            }
        ]
        
        msg_with_sources = MessageRepository.create(
            db=db,
            conversation_id=conv.id,
            role="assistant",
            content="Yes, we offer refunds and have Margherita pizza.",
            sources=test_sources
        )
        
        # Message with empty sources
        msg_empty_sources = MessageRepository.create(
            db=db,
            conversation_id=conv.id,
            role="assistant",
            content="How can I help you?",
            sources=[]
        )

        # Retrieve messages and verify sources list survives SQL round-trip
        db.expire_all()
        retrieved_messages = MessageRepository.list_by_conversation(db, conv.id)
        assert len(retrieved_messages) == 2
        
        # Verify message 1 sources
        m1 = retrieved_messages[0]
        assert m1.sources is not None
        assert len(m1.sources) == 2
        assert m1.sources[0]["title"] == "Refund Guide"
        assert m1.sources[0]["document_type"] == "refund_policy"
        assert m1.sources[0]["document_id"] == "doc-uuid-1"
        assert m1.sources[0]["snippet"] == "Orders cancelled within 5 mins qualify for a refund."
        
        assert m1.sources[1]["title"] == "Pizza Menu"
        assert m1.sources[1]["document_type"] == "menu"
        assert m1.sources[1]["document_id"] == "doc-uuid-2"
        assert m1.sources[1]["snippet"] == "Margherita: tomato sauce, fresh mozzarella, basil."
        
        # Verify message 2 empty sources
        m2 = retrieved_messages[1]
        assert m2.sources == [] or m2.sources is None
        
        print("✓ Confirmed: RAG source metadata structures persist and reload without data loss.")

        # =====================================================================
        # TEST 2: Streamlit Frontend Source Citation Renderer
        # =====================================================================
        print("\n3. Testing Streamlit frontend citation expander rendering...")
        
        # Reset mock counters
        mock_markdown.reset_mock()
        mock_expander.reset_mock()
        mock_caption.reset_mock()
        mock_info.reset_mock()
        
        # Set up active conversation session and mock history loaded in state
        mock_state.selected_restaurant = restaurant.id
        mock_state.current_chat_restaurant = restaurant.id
        mock_state.active_conversation_id = conv.id
        
        # Seed message history logs in frontend session state
        mock_state.messages = [
            {
                "role": "user",
                "content": "Hi, do you offer refunds?",
                "sources": [],
                "timestamp": datetime.utcnow().isoformat()
            },
            {
                "role": "assistant",
                "content": "Yes, we offer refunds.",
                "sources": [
                    {
                        "document_id": "doc-uuid-1",
                        "title": "Refund Guide",
                        "document_type": "refund_policy",
                        "snippet": "Orders cancelled within 5 mins qualify for a refund."
                    }
                ],
                "timestamp": datetime.utcnow().isoformat()
            },
            {
                "role": "assistant",
                "content": "Is there anything else?",
                "sources": [], # empty source lists must NOT render UI elements
                "timestamp": datetime.utcnow().isoformat()
            }
        ]

        # Configure selectbox to return the correct restaurant name to bypass page transitions
        mock_selectbox.return_value = "Gourmet Pizza Place"
        
        # Trigger rendering the customer dashboard containing the message loop
        render_customer_dashboard()
        
        # 1. Verify st.expander is called exactly once with the citations label.
        assert mock_expander.call_count == 1, f"Expected expander to be called exactly 1 time, but was called {mock_expander.call_count} times."
        mock_expander.assert_called_with("View sources & citations", expanded=False)
        
        # 2. Verify citation metadata details are formatted correctly and output inside the expander
        # It should call st.markdown with document title and capitalized type
        # Let's collect markdown arguments
        markdown_calls = [call[0][0] for call in mock_markdown.call_args_list]
        
        # Verify document title and type formatting
        expected_markdown = "**[1] Refund Guide** (REFUND_POLICY)"
        assert any(expected_markdown in str(c) for c in markdown_calls), f"Expected markdown to contain '{expected_markdown}'"
        
        # Verify Caption is called with Source ID
        mock_caption.assert_called_with("Source ID: `doc-uuid-1`")
        
        # Verify Info is called with snippet text (assert_any_call: the dashboard
        # emits other st.info calls too, e.g. an empty-orders notice, so we check
        # the citation snippet was rendered at some point rather than last).
        mock_info.assert_any_call("Orders cancelled within 5 mins qualify for a refund.")
        
        # 3. Verify empty source list (message 3) did not trigger another expander
        # This is implicitly checked because call_count is exactly 1.
        
        print("✓ Confirmed: Streamlit expanders render correctly for assistant messages with sources.")
        print("✓ Confirmed: Empty source lists are ignored (no UI elements rendered).")
        print("✓ Confirmed: Historical messages successfully parse and output citation elements.")

    finally:
        db.close()
        # Clean up database files and folder
        if os.path.exists(test_db_path):
            os.remove(test_db_path)

    print("\n✓ ALL DEF-01 REMEDIATION CITATION RENDERING TESTS PASSED SUCCESSFULLY!")
    print("=" * 80)
    sys.exit(0)

if __name__ == "__main__":
    run_source_rendering_tests()
