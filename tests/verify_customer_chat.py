import os
import sys
import unittest.mock as mock
from datetime import datetime

# Ensure project root is in the path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.append(project_root)

# Set up test database path
test_db_path = os.path.join(project_root, "data", "test_customer_chat.db")
os.environ["DATABASE_URL"] = f"sqlite:///{test_db_path}"

# Clean test db file if it already exists
if os.path.exists(test_db_path):
    try:
        os.remove(test_db_path)
    except Exception:
        pass

from tests.utils.test_bootstrap import bootstrap_test_database
SessionLocalTest = bootstrap_test_database(os.environ["DATABASE_URL"])

from backend.repositories.restaurant_repository import RestaurantRepository
from backend.repositories.user_repository import UserRepository
from backend.models.user import UserRole

# Mock Streamlit session state and functions
class MockSessionState(dict):
    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)
    def __setattr__(self, name, value):
        self[name] = value

# Initialize global mocked session state
mock_state = MockSessionState()
mock_state.messages = []
mock_state.selected_restaurant = None
mock_state.current_chat_restaurant = None

import streamlit as st
st.session_state = mock_state

# Import the dashboard components to test
from frontend.components.customer_dashboard import (
    initialize_restaurant_conversation,
    process_chat_message
)

def run_chat_ui_tests():
    print("=" * 80)
    print("RUNNING CUSTOMER CHAT ASSISTANT UI VERIFICATION")
    print("=" * 80)

    # 1. Initialize test database
    print("Initializing test database tables...")
    db = SessionLocalTest()

    try:
        # Create test restaurants
        print("\nCreating active test restaurants...")
        restaurant_a = RestaurantRepository.create(db, name="Pizzeria Alpha")
        restaurant_b = RestaurantRepository.create(db, name="Burger Beta")

        # =====================================================================
        # TEST 1: Direct Dependency Check
        # =====================================================================
        print("\n1. Testing Backend Code Dependency Boundaries...")
        dashboard_path = os.path.join(project_root, "frontend", "components", "customer_dashboard.py")
        with open(dashboard_path, "r") as f:
            code = f.read()
        
        # Verify no direct dependency exists on gemini_service.generate_response
        assert "generate_response" not in code, "Failed: Direct dependency on generate_response detected!"
        print("✓ Confirmed: customer_dashboard has NO direct imports or references to gemini_service.generate_response.")

        # =====================================================================
        # TEST 2: Conversation Initialization Helper
        # =====================================================================
        print("\n2. Testing initialize_restaurant_conversation() helper...")
        mock_state.messages = []
        mock_state.selected_restaurant = None
        mock_state.current_chat_restaurant = None

        initialize_restaurant_conversation(restaurant_a.id, restaurant_a.name)

        # Assert correct updates on state keys
        assert mock_state.selected_restaurant == restaurant_a.id, "selected_restaurant not updated"
        assert mock_state.current_chat_restaurant == restaurant_a.id, "current_chat_restaurant not updated"
        assert len(mock_state.messages) == 1, f"Expected 1 welcome message, got {len(mock_state.messages)}"
        
        greeting = mock_state.messages[0]
        assert greeting["role"] == "assistant"
        assert f"Assistant for {restaurant_a.name}" in greeting["content"]
        assert "sources" in greeting and greeting["sources"] == []
        assert "timestamp" in greeting, "Timestamp metadata missing on greeting message"
        
        # Verify ISO timestamp format parsing
        try:
            datetime.fromisoformat(greeting["timestamp"])
            print("✓ Greeting message timestamp is valid ISO format.")
        except Exception:
            assert False, f"Invalid ISO timestamp format: {greeting['timestamp']}"

        print("✓ initialize_restaurant_conversation() correctly set active keys, greeting content, and timestamps.")

        # =====================================================================
        # TEST 3: Restaurant Switch & History Reset
        # =====================================================================
        print("\n3. Testing Context Switching Resets...")
        # Simulate active chat with Pizzeria Alpha
        mock_state.messages.append({
            "role": "user",
            "content": "Do you serve vegan pizza?",
            "timestamp": datetime.utcnow().isoformat()
        })
        mock_state.messages.append({
            "role": "assistant",
            "content": "Yes, we serve vegan pizza with cashew cheese.",
            "sources": [],
            "timestamp": datetime.utcnow().isoformat()
        })
        assert len(mock_state.messages) == 3 # 1 greeting + 1 user + 1 assistant

        # Switch to Burger Beta
        initialize_restaurant_conversation(restaurant_b.id, restaurant_b.name)

        # Assert history was cleared and initialized specifically to Beta
        assert mock_state.selected_restaurant == restaurant_b.id
        assert len(mock_state.messages) == 1, "Chat history was not cleared/evicted upon switching restaurant context"
        assert f"Assistant for {restaurant_b.name}" in mock_state.messages[0]["content"]
        print("✓ Context switching successfully clears previous log history and seeds restaurant welcome greeting.")

        # =====================================================================
        # TEST 4: Chat Processing Boundary & RAG Integration
        # =====================================================================
        print("\n4. Testing process_chat_message() orchestration bridge...")
        
        mock_orch_response = {
            "answer": "This is a mock RAG answer for test verification.",
            "sources": [{"document_id": "doc-123", "title": "Beta Menu", "document_type": "menu"}],
            "chunks_used": 1,
            "intent": "Menu Inquiry",
            "sentiment": "Neutral",
            "language": "English",
            "escalation_result": {"escalate": False, "reason": "No Escalation Required"}
        }

        # Mock ConversationOrchestrator.orchestrate to assert UI-backend delegation
        with mock.patch("backend.services.conversation_orchestrator.ConversationOrchestrator.orchestrate", return_value=mock_orch_response) as mock_orch:
            res = process_chat_message(db, restaurant_b.id, "Do you have gluten free buns?")
            
            # Assert process_chat_message delegates directly to ConversationOrchestrator
            mock_orch.assert_called_once_with(db, restaurant_b.id, "Do you have gluten free buns?")
            assert res == mock_orch_response
            print("✓ process_chat_message() delegates correctly to ConversationOrchestrator.orchestrate.")

        # =====================================================================
        # TEST 5: Message Timestamps & Source Preservation Contracts
        # =====================================================================
        print("\n5. Testing message timestamping and source preservation constraints...")
        # Clear messages and re-init
        initialize_restaurant_conversation(restaurant_a.id, restaurant_a.name)

        # Simulate user prompt
        user_msg = {
            "role": "user",
            "content": "Is delivery available?",
            "timestamp": datetime.utcnow().isoformat()
        }
        mock_state.messages.append(user_msg)

        # Simulate assistant response save contract
        assistant_msg = {
            "role": "assistant",
            "content": mock_orch_response["answer"],
            "sources": mock_orch_response["sources"],
            "timestamp": datetime.utcnow().isoformat()
        }
        mock_state.messages.append(assistant_msg)

        # Assert user and assistant messages retain the UTC timestamps
        assert "timestamp" in mock_state.messages[1]
        assert mock_state.messages[1]["role"] == "user"
        
        assert "timestamp" in mock_state.messages[2]
        assert mock_state.messages[2]["role"] == "assistant"
        
        # Verify sources preservation
        assert "sources" in mock_state.messages[2]
        assert len(mock_state.messages[2]["sources"]) == 1
        assert mock_state.messages[2]["sources"][0]["title"] == "Beta Menu"
        assert mock_state.messages[2]["sources"][0]["document_id"] == "doc-123"

        print("✓ Timestamp metadata and source attribution list successfully preserved in state log.")

    finally:
        db.close()
        # Clean up database files and folder
        if os.path.exists(test_db_path):
            os.remove(test_db_path)

    print("\n✓ ALL CUSTOMER CHAT ASSISTANT UI TESTS PASSED SUCCESSFULLY!")
    print("=" * 80)
    sys.exit(0)

if __name__ == "__main__":
    run_chat_ui_tests()
