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
from backend.services.escalation_service import EscalationService
from backend.services.conversation_service import ConversationService
from backend.models.user import UserRole

class TestEscalationWorkflow(unittest.TestCase):
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

    def tearDown(self):
        self.db.close()

    def test_workflow_lifecycle(self):
        # 1. Create escalation
        esc = EscalationService.create_escalation(
            self.db,
            conversation_id=self.conversation.id,
            reason="Refund Request"
        )
        self.assertEqual(esc.status, "pending")
        self.assertEqual(esc.priority, "high")  # Mapped high
        
        # Check conversation status synchronized to escalated
        conv = ConversationRepository.get_by_id(self.db, self.conversation.id)
        self.assertEqual(conv.status, "escalated")

        # 2. Add notes
        EscalationService.add_notes(self.db, esc.id, self.manager, "Notes addition test")
        self.assertEqual(esc.notes, "Notes addition test")

        # 3. Claim escalation
        EscalationService.claim_escalation(self.db, esc.id, self.manager)
        self.assertEqual(esc.status, "claimed")
        self.assertEqual(esc.assigned_to, self.manager.id)

        # 4. Resolve escalation
        EscalationService.resolve_escalation(self.db, esc.id, self.manager, "Resolved by processing refund.")
        self.assertEqual(esc.status, "resolved")
        self.assertEqual(esc.resolved_by, self.manager.id)
        self.assertEqual(esc.resolution_summary, "Resolved by processing refund.")

        # Check conversation status synchronized to resolved
        self.db.refresh(conv)
        self.assertEqual(conv.status, "resolved")

    def test_idempotent_creation(self):
        esc1 = EscalationService.create_escalation(self.db, self.conversation.id, "Refund Request")
        esc2 = EscalationService.create_escalation(self.db, self.conversation.id, "Negative Sentiment")
        
        # Second call returns the first one (idempotency)
        self.assertEqual(esc1.id, esc2.id)
        self.assertEqual(esc1.reason, "Refund Request")

if __name__ == "__main__":
    unittest.main()
