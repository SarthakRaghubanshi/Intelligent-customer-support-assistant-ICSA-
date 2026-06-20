import os
import sys
import unittest

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.append(project_root)

from tests.utils.test_bootstrap import bootstrap_test_database
from backend.repositories.restaurant_repository import RestaurantRepository
from backend.repositories.conversation_repository import ConversationRepository
from backend.repositories.user_repository import UserRepository
from backend.repositories.message_repository import MessageRepository
from backend.services.escalation_service import EscalationService
from backend.models.user import UserRole

class TestEscalationReviewCenter(unittest.TestCase):
    def setUp(self):
        self.SessionLocal = bootstrap_test_database()
        self.db = self.SessionLocal()
        
        # Seed test entities
        self.restaurant = RestaurantRepository.create(self.db, name="Test Restaurant")
        self.manager = UserRepository.create(
            self.db,
            email="manager@test.com",
            password_raw="password123",
            role=UserRole.RESTAURANT,
            restaurant_id=self.restaurant.id
        )
        self.conversation = ConversationRepository.create(
            self.db,
            customer_id=None,
            restaurant_id=self.restaurant.id
        )
        # Create user message transcript
        self.msg1 = MessageRepository.create(
            self.db,
            conversation_id=self.conversation.id,
            role="user",
            content="I want to speak with a human support agent please."
        )
        self.msg2 = MessageRepository.create(
            self.db,
            conversation_id=self.conversation.id,
            role="assistant",
            content="Sure, connecting you to a manager..."
        )

    def tearDown(self):
        self.db.close()

    def test_transcript_loading(self):
        # Create escalation event
        esc = EscalationService.create_escalation(
            self.db,
            conversation_id=self.conversation.id,
            reason="Human Assistance Requested"
        )
        
        # Load transcript via service
        transcript = EscalationService.get_transcript(self.db, esc.id, self.manager)
        self.assertEqual(len(transcript), 2)
        self.assertEqual(transcript[0].content, "I want to speak with a human support agent please.")
        self.assertEqual(transcript[1].content, "Sure, connecting you to a manager...")

    def test_filtering_and_listings(self):
        esc = EscalationService.create_escalation(
            self.db,
            conversation_id=self.conversation.id,
            reason="Human Assistance Requested"
        )
        
        # Get escalations lists
        all_esc = EscalationService.get_escalations_for_restaurant(self.db, self.manager)
        self.assertEqual(len(all_esc), 1)
        self.assertEqual(all_esc[0].id, esc.id)

if __name__ == "__main__":
    unittest.main()
