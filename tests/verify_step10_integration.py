import os
import sys
import unittest
import unittest.mock as mock

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.append(project_root)

from tests.utils.test_bootstrap import bootstrap_test_database
from backend.repositories.restaurant_repository import RestaurantRepository
from backend.repositories.conversation_repository import ConversationRepository
from backend.repositories.message_repository import MessageRepository
from backend.repositories.escalation_repository import EscalationRepository
from backend.services.conversation_orchestrator import ConversationOrchestrator
from backend.services.conversation_service import ConversationService
from backend.models.user import User, UserRole

class MockResponse:
    def __init__(self, text):
        self.text = text

def mock_generate_content(*args, **kwargs):
    return MockResponse("This is a mock response from the Gemini model.")

class TestStep10Integration(unittest.TestCase):
    def setUp(self):
        self.SessionLocal = bootstrap_test_database()
        self.db = self.SessionLocal()
        
        # Seed test entities
        self.restaurant = RestaurantRepository.create(self.db, name="Test Restaurant")
        self.conversation = ConversationRepository.create(
            self.db,
            customer_id=None,
            restaurant_id=self.restaurant.id
        )

    def tearDown(self):
        self.db.close()

    def test_pipeline_escalation_integration(self):
        query = "Can I get a refund for my pizza? It was completely cold."
        
        # Create user message turn
        MessageRepository.create(
            self.db,
            conversation_id=self.conversation.id,
            role="user",
            content=query
        )

        # Mock LLM API and invoke orchestrator passing conversation_id
        with mock.patch("google.generativeai.generative_models.GenerativeModel.generate_content", side_effect=mock_generate_content):
            response = ConversationOrchestrator.orchestrate(
                db=self.db,
                restaurant_id=self.restaurant.id,
                question=query,
                conversation_id=self.conversation.id
            )
            
            # Verify the response contract contains the correct classification
            self.assertEqual(response["intent"], "Refund Inquiry")
            self.assertTrue(response["escalation_result"]["escalate"])
            self.assertEqual(response["escalation_result"]["reason"], "Refund Request")

            # Verify that the DB record was auto-created
            escalation = EscalationRepository.get_by_conversation(self.db, self.conversation.id)
            self.assertIsNotNone(escalation)
            self.assertEqual(escalation.reason, "Refund Request")
            self.assertEqual(escalation.priority, "high")
            self.assertEqual(escalation.status, "pending")

            # Verify conversation status was synchronized to 'escalated'
            conv = ConversationRepository.get_by_id(self.db, self.conversation.id)
            self.assertEqual(conv.status, "escalated")

if __name__ == "__main__":
    unittest.main()
