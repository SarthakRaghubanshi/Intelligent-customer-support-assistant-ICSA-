import os
import sys
import unittest

# Add project root to sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.append(project_root)

from tests.utils.test_bootstrap import bootstrap_test_database
from backend.repositories.restaurant_repository import RestaurantRepository
from backend.repositories.conversation_repository import ConversationRepository
from backend.repositories.user_repository import UserRepository
from backend.repositories.escalation_repository import EscalationRepository
from backend.models.escalation_event import EscalationEvent
from backend.models.user import UserRole

class TestEscalationEventStorage(unittest.TestCase):
    def setUp(self):
        # Bootstrap a clean in-memory SQLite DB
        self.SessionLocal = bootstrap_test_database()
        self.db = self.SessionLocal()
        
        # Seed test entities
        self.restaurant = RestaurantRepository.create(self.db, name="Test Restaurant")
        self.user = UserRepository.create(
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

    def test_escalation_crud(self):
        # 1. Create EscalationEvent
        esc = EscalationRepository.create(
            self.db,
            conversation_id=self.conversation.id,
            reason="Refund Request",
            priority="high"
        )
        self.assertIsNotNone(esc.id)
        self.assertEqual(esc.conversation_id, self.conversation.id)
        self.assertEqual(esc.reason, "Refund Request")
        self.assertEqual(esc.priority, "high")
        self.assertEqual(esc.status, "pending")
        self.assertIsNotNone(esc.created_at)

        # 2. Get by ID
        fetched = EscalationRepository.get_by_id(self.db, esc.id)
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.reason, "Refund Request")

        # 3. Get by Conversation ID
        fetched_conv = EscalationRepository.get_by_conversation(self.db, self.conversation.id)
        self.assertIsNotNone(fetched_conv)
        self.assertEqual(fetched_conv.id, esc.id)

        # 4. List by Restaurant
        list_rest = EscalationRepository.list_by_restaurant(self.db, self.restaurant.id)
        self.assertEqual(len(list_rest), 1)
        self.assertEqual(list_rest[0].id, esc.id)

        # 5. List by Status
        list_status_pending = EscalationRepository.list_by_status(self.db, self.restaurant.id, "pending")
        self.assertEqual(len(list_status_pending), 1)
        
        list_status_claimed = EscalationRepository.list_by_status(self.db, self.restaurant.id, "claimed")
        self.assertEqual(len(list_status_claimed), 0)

        # 6. Update Notes
        updated = EscalationRepository.update_notes(self.db, esc.id, "Customer requested supervisor support")
        self.assertEqual(updated.notes, "Customer requested supervisor support")

        # 7. Claim
        claimed = EscalationRepository.claim(self.db, esc.id, self.user.id)
        self.assertEqual(claimed.status, "claimed")
        self.assertEqual(claimed.assigned_to, self.user.id)
        self.assertIsNotNone(claimed.claimed_at)

        # 8. Resolve
        resolved = EscalationRepository.resolve(self.db, esc.id, self.user.id, "Refund processed.")
        self.assertEqual(resolved.status, "resolved")
        self.assertEqual(resolved.resolved_by, self.user.id)
        self.assertEqual(resolved.resolution_summary, "Refund processed.")
        self.assertIsNotNone(resolved.resolved_at)

    def test_cascade_delete(self):
        # Create an escalation
        esc = EscalationRepository.create(
            self.db,
            conversation_id=self.conversation.id,
            reason="Refund Request",
            priority="high"
        )
        self.assertIsNotNone(EscalationRepository.get_by_id(self.db, esc.id))

        # Delete conversation
        self.db.delete(self.conversation)
        self.db.commit()

        # Escalation should be deleted automatically via ON DELETE CASCADE constraint
        self.assertIsNone(EscalationRepository.get_by_id(self.db, esc.id))

if __name__ == "__main__":
    unittest.main()
