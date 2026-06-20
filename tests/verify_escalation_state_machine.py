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
from backend.repositories.escalation_repository import EscalationRepository
from backend.services.escalation_service import EscalationService
from backend.models.user import UserRole

class TestEscalationStateMachine(unittest.TestCase):
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
        self.manager_other = UserRepository.create(
            self.db,
            email="manager_other@test.com",
            password_raw="password123",
            role=UserRole.RESTAURANT,
            restaurant_id=self.restaurant.id
        )
        self.conversation = ConversationRepository.create(
            self.db,
            customer_id=None,
            restaurant_id=self.restaurant.id
        )
        self.esc = EscalationService.create_escalation(
            self.db,
            conversation_id=self.conversation.id,
            reason="Refund Request"
        )

    def tearDown(self):
        self.db.close()

    def test_invalid_transitions(self):
        # Initial status is pending
        self.assertEqual(self.esc.status, "pending")

        # 1. Try resolving pending escalation (Invalid)
        with self.assertRaises(ValueError):
            EscalationService.resolve_escalation(self.db, self.esc.id, self.manager, "Resolving pending")

        # 2. Claim pending (Valid)
        EscalationService.claim_escalation(self.db, self.esc.id, self.manager)
        self.assertEqual(self.esc.status, "claimed")

        # 3. Try claiming an already claimed escalation (Invalid)
        with self.assertRaises(ValueError):
            EscalationService.claim_escalation(self.db, self.esc.id, self.manager)

        # 4. Try re-claiming with another manager (Invalid)
        with self.assertRaises(ValueError):
            EscalationService.claim_escalation(self.db, self.esc.id, self.manager_other)

        # 5. Try resolving with non-assigned manager (Invalid)
        with self.assertRaises(PermissionError):
            EscalationService.resolve_escalation(self.db, self.esc.id, self.manager_other, "Try resolving")

        # 6. Resolve with assigned manager (Valid)
        EscalationService.resolve_escalation(self.db, self.esc.id, self.manager, "Resolving claimed")
        self.assertEqual(self.esc.status, "resolved")

        # 7. Try claiming a resolved escalation (Invalid)
        with self.assertRaises(ValueError):
            EscalationService.claim_escalation(self.db, self.esc.id, self.manager)

        # 8. Try adding notes to a resolved escalation (Invalid)
        with self.assertRaises(ValueError):
            EscalationService.add_notes(self.db, self.esc.id, self.manager, "Notes after resolve")

if __name__ == "__main__":
    unittest.main()
