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
from backend.models.user import UserRole

class TestEscalationTenantSecurity(unittest.TestCase):
    def setUp(self):
        self.SessionLocal = bootstrap_test_database()
        self.db = self.SessionLocal()
        
        # Restaurant 1 and Manager 1
        self.rest1 = RestaurantRepository.create(self.db, name="Restaurant One")
        self.mgr1 = UserRepository.create(
            self.db,
            email="mgr1@test.com",
            password_raw="password123",
            role=UserRole.RESTAURANT,
            restaurant_id=self.rest1.id
        )
        self.conv1 = ConversationRepository.create(
            self.db,
            customer_id=None,
            restaurant_id=self.rest1.id
        )
        self.esc1 = EscalationService.create_escalation(
            self.db,
            conversation_id=self.conv1.id,
            reason="Refund Request"
        )

        # Restaurant 2 and Manager 2
        self.rest2 = RestaurantRepository.create(self.db, name="Restaurant Two")
        self.mgr2 = UserRepository.create(
            self.db,
            email="mgr2@test.com",
            password_raw="password123",
            role=UserRole.RESTAURANT,
            restaurant_id=self.rest2.id
        )
        
        # Customer Role
        self.customer = UserRepository.create(
            self.db,
            email="customer@test.com",
            password_raw="password123",
            role=UserRole.CUSTOMER
        )

        # Admin Role
        self.admin = UserRepository.create(
            self.db,
            email="admin@test.com",
            password_raw="password123",
            role=UserRole.ADMIN
        )

    def tearDown(self):
        self.db.close()

    def test_cross_tenant_isolation(self):
        # Manager 1 can claim escalation from Restaurant 1
        EscalationService.claim_escalation(self.db, self.esc1.id, self.mgr1)
        self.assertEqual(self.esc1.status, "claimed")

        # Create a new conversation and escalation for Restaurant 2
        conv2 = ConversationRepository.create(
            self.db,
            customer_id=None,
            restaurant_id=self.rest2.id
        )
        esc2 = EscalationService.create_escalation(
            self.db,
            conversation_id=conv2.id,
            reason="Refund Request"
        )

        # Manager 1 trying to claim escalation from Restaurant 2 (Should raise PermissionError)
        with self.assertRaises(PermissionError):
            EscalationService.claim_escalation(self.db, esc2.id, self.mgr1)

    def test_customer_role_rejection(self):
        # Customer trying to view escalations list (Should raise PermissionError)
        with self.assertRaises(PermissionError):
            EscalationService.get_escalations_for_restaurant(self.db, self.customer)

        # Customer trying to claim escalation (Should raise PermissionError)
        with self.assertRaises(PermissionError):
            EscalationService.claim_escalation(self.db, self.esc1.id, self.customer)

    def test_admin_override(self):
        # Admin can view all escalations
        all_escalations = EscalationService.get_escalations_for_restaurant(self.db, self.admin)
        self.assertGreaterEqual(len(all_escalations), 1)

if __name__ == "__main__":
    unittest.main()
