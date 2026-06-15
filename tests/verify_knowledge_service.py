import os
import sys

# Ensure project root is in the path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.append(project_root)

# Force a distinct test DB for validation
test_db_path = os.path.join(project_root, "data", "test_kb_service_saas.db")
os.environ["DATABASE_URL"] = f"sqlite:///{test_db_path}"

# Clean test db file if it already exists
if os.path.exists(test_db_path):
    os.remove(test_db_path)

from backend.database.database import engine, Base, SessionLocal
from backend.models.user import User, UserRole
from backend.repositories.restaurant_repository import RestaurantRepository
from backend.repositories.user_repository import UserRepository
from backend.services.auth_service import AuthService
from backend.services.knowledge_service import KnowledgeService

def run_knowledge_service_tests():
    print("=" * 80)
    print("RUNNING RESTAURANT KNOWLEDGE SERVICE VERIFICATION")
    print("=" * 80)

    # 1. Initialize test database
    print("Initializing test database tables...")
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        # 2. Create test restaurants
        print("\nCreating active test restaurants...")
        restaurant_a = RestaurantRepository.create(db, name="Restaurant A")
        restaurant_b = RestaurantRepository.create(db, name="Restaurant B")

        # 3. Create test users
        print("\nCreating test users...")
        admin_user = UserRepository.create(db, "admin@saas.com", "pass1234", UserRole.ADMIN)
        rest_a_user = UserRepository.create(
            db, "rest_a@saas.com", "pass1234", UserRole.RESTAURANT, restaurant_id=restaurant_a.id
        )
        rest_b_user = UserRepository.create(
            db, "rest_b@saas.com", "pass1234", UserRole.RESTAURANT, restaurant_id=restaurant_b.id
        )
        customer_user = UserRepository.create(db, "customer@saas.com", "pass1234", UserRole.CUSTOMER)

        # 4. Generate access tokens
        admin_token = AuthService.create_access_token(admin_user.id, admin_user.email, admin_user.role.value)
        rest_a_token = AuthService.create_access_token(rest_a_user.id, rest_a_user.email, rest_a_user.role.value)
        rest_b_token = AuthService.create_access_token(rest_b_user.id, rest_b_user.email, rest_b_user.role.value)
        customer_token = AuthService.create_access_token(customer_user.id, customer_user.email, customer_user.role.value)

        # 5. Verify CRUD Operations via KnowledgeService
        print("\n1. Testing CRUD operations via KnowledgeService...")
        
        # Test document type validation (service level check)
        try:
            KnowledgeService.create_document(
                db, rest_a_token, restaurant_a.id, "Invalid Doc", "Some content", "invalid_type"
            )
            assert False, "Failed: Allowed invalid document type"
        except ValueError as e:
            print(f"✓ Invalid document type caught correctly: {e}")

        # Create docs
        doc_a_menu = KnowledgeService.create_document(
            db, rest_a_token, restaurant_a.id, "Restaurant A Menu", "Mains: Tacos", "menu"
        )
        doc_a_faq = KnowledgeService.create_document(
            db, rest_a_token, restaurant_a.id, "Restaurant A FAQ", "Parking details here...", "faq"
        )
        doc_a_refund = KnowledgeService.create_document(
            db, rest_a_token, restaurant_a.id, "Restaurant A Refund Policy", "Standard policy info...", "refund_policy"
        )

        assert doc_a_menu.id is not None
        assert doc_a_menu.title == "Restaurant A Menu"
        assert doc_a_menu.document_type == "menu"
        print("✓ Document creation and document_type validation passed.")

        # Read / Get
        read_doc = KnowledgeService.get_document(db, rest_a_token, doc_a_menu.id)
        assert read_doc is not None
        assert read_doc.title == "Restaurant A Menu"
        print("✓ Document retrieval passed.")

        # Update
        updated = KnowledgeService.update_document(
            db, rest_a_token, doc_a_menu.id, {"title": "Updated Menu Title", "content": "Mains: Enchiladas"}
        )
        assert updated.title == "Updated Menu Title"
        assert updated.content == "Mains: Enchiladas"
        
        # Verify document_type validation during update
        try:
            KnowledgeService.update_document(db, rest_a_token, doc_a_menu.id, {"document_type": "bad_type"})
            assert False, "Failed: Allowed invalid document type during update"
        except ValueError as e:
            print(f"✓ Invalid document type update blocked: {e}")
        print("✓ Document update passed.")

        # Delete (Soft Delete)
        delete_ok = KnowledgeService.delete_document(db, rest_a_token, doc_a_faq.id)
        assert delete_ok is True
        
        read_deleted = KnowledgeService.get_document(db, rest_a_token, doc_a_faq.id)
        assert read_deleted is None
        print("✓ Document soft-deletion passed.")

        # 6. Verify Pagination
        print("\n2. Testing Pagination parameters (limit/offset) & document count...")
        # Add 3 more docs to have enough items
        for i in range(3):
            KnowledgeService.create_document(
                db, rest_a_token, restaurant_a.id, f"Extra Doc {i}", "Content info...", "other"
            )

        # Count should be 5 active documents (Menu, Refund, and 3 Extra Docs)
        total_count = KnowledgeService.get_document_count(db, rest_a_token, restaurant_a.id)
        assert total_count == 5, f"Expected 5 documents, got {total_count}"
        print("✓ Document count helper passed.")

        # List with limit=2, offset=0
        list_p1 = KnowledgeService.list_documents(db, rest_a_token, restaurant_a.id, limit=2, offset=0)
        assert len(list_p1) == 2
        
        # List with limit=2, offset=2
        list_p2 = KnowledgeService.list_documents(db, rest_a_token, restaurant_a.id, limit=2, offset=2)
        assert len(list_p2) == 2
        
        # List with limit=2, offset=4
        list_p3 = KnowledgeService.list_documents(db, rest_a_token, restaurant_a.id, limit=2, offset=4)
        assert len(list_p3) == 1
        
        # Asserts that they do not overlap
        doc_ids_p1 = [d.id for d in list_p1]
        doc_ids_p2 = [d.id for d in list_p2]
        doc_ids_p3 = [d.id for d in list_p3]
        
        for d_id in doc_ids_p1:
            assert d_id not in doc_ids_p2
            assert d_id not in doc_ids_p3
        for d_id in doc_ids_p2:
            assert d_id not in doc_ids_p3
            
        print("✓ Pagination limit/offset verification passed.")

        # 7. Verify Search
        print("\n3. Testing Document search by title...")
        search_results = KnowledgeService.search_documents(db, rest_a_token, restaurant_a.id, "Extra")
        assert len(search_results) == 3
        assert all("Extra" in r.title for r in search_results)
        print("✓ Search functionality verified.")

        # 8. Verify Tenant Isolation
        print("\n4. Testing Tenant Isolation boundaries...")
        
        # Create doc for Restaurant B
        doc_b = KnowledgeService.create_document(
            db, rest_b_token, restaurant_b.id, "Restaurant B Doc", "Content info...", "menu"
        )

        # Restaurant A accessing Restaurant B doc -> Blocked
        try:
            KnowledgeService.get_document(db, rest_a_token, doc_b.id)
            assert False, "Failed: Restaurant A user accessed Restaurant B document"
        except PermissionError as e:
            print(f"✓ Cross-tenant read access blocked correctly: {e}")

        # Restaurant A listing Restaurant B docs -> Blocked
        try:
            KnowledgeService.list_documents(db, rest_a_token, restaurant_b.id)
            assert False, "Failed: Restaurant A user listed Restaurant B documents"
        except PermissionError as e:
            print(f"✓ Cross-tenant list access blocked correctly: {e}")

        # Restaurant A updating Restaurant B doc -> Blocked
        try:
            KnowledgeService.update_document(db, rest_a_token, doc_b.id, {"title": "Tampered Title"})
            assert False, "Failed: Restaurant A user updated Restaurant B document"
        except PermissionError as e:
            print(f"✓ Cross-tenant update access blocked correctly: {e}")

        # 9. Verify Admin Override
        print("\n5. Testing Admin Override features...")
        admin_list = KnowledgeService.list_documents(db, admin_token, restaurant_a.id)
        assert len(admin_list) == 5
        
        admin_read_b = KnowledgeService.get_document(db, admin_token, doc_b.id)
        assert admin_read_b is not None
        assert admin_read_b.title == "Restaurant B Doc"
        print("✓ Admin override verified successfully.")

        # 10. Verify Customer Denial
        print("\n6. Testing Customer Access Denials...")
        try:
            KnowledgeService.list_documents(db, customer_token, restaurant_a.id)
            assert False, "Failed: Customer was allowed to list documents"
        except PermissionError as e:
            print(f"✓ Customer list access blocked: {e}")

        try:
            KnowledgeService.create_document(
                db, customer_token, restaurant_a.id, "Customer Doc", "Content info...", "menu"
            )
            assert False, "Failed: Customer was allowed to create document"
        except PermissionError as e:
            print(f"✓ Customer create access blocked: {e}")

        # 11. Verify Inactive Restaurant Rejection
        print("\n7. Testing Inactive restaurant rejections...")
        restaurant_a.is_active = False
        db.commit()

        try:
            KnowledgeService.list_documents(db, admin_token, restaurant_a.id)
            assert False, "Failed: Allowed access to inactive restaurant documents"
        except ValueError as e:
            print(f"✓ Inactive restaurant access rejected as expected: {e}")

    finally:
        db.close()
        # Clean up database file
        if os.path.exists(test_db_path):
            os.remove(test_db_path)

    print("\n✓ ALL RESTAURANT KNOWLEDGE SERVICE VERIFICATION TESTS PASSED SUCCESSFULLY!")
    print("=" * 80)
    sys.exit(0)

if __name__ == "__main__":
    run_knowledge_service_tests()
