import os
import sys

# Ensure project root is in the path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.append(project_root)

# Force a distinct test DB for validation
test_db_path = os.path.join(project_root, "data", "test_kb_saas.db")
os.environ["DATABASE_URL"] = f"sqlite:///{test_db_path}"

# Clean test db file if it already exists
if os.path.exists(test_db_path):
    os.remove(test_db_path)

from backend.database.database import engine, Base, SessionLocal
from backend.models.user import User, UserRole
from backend.models.restaurant import Restaurant
from backend.models.knowledge_document import KnowledgeDocument
from backend.repositories.restaurant_repository import RestaurantRepository
from backend.repositories.user_repository import UserRepository
from backend.repositories.knowledge_repository import KnowledgeRepository
from backend.services.auth_service import AuthService

# =====================================================================
# SIMULATED SERVICE LAYER WRAPPERS
# Mimics backend services layer orchestrating validation and database queries.
# =====================================================================

def service_create_document(db, token, restaurant_id, title, content, doc_type):
    # Enforces active check and tenant isolation boundary via AuthService helper
    AuthService.validate_tenant_access(db, token, restaurant_id)
    return KnowledgeRepository.create(db, restaurant_id, title, content, doc_type)

def service_get_document(db, token, doc_id):
    # Fetch document first
    doc = db.query(KnowledgeDocument).filter(
        KnowledgeDocument.id == doc_id,
        KnowledgeDocument.deleted_at.is_(None)
    ).first()
    if not doc:
        return None
    # Validate tenant access to the document's restaurant context
    AuthService.validate_tenant_access(db, token, doc.restaurant_id)
    return doc

def service_list_documents(db, token, restaurant_id):
    # Enforces active check and tenant isolation boundary via AuthService helper
    AuthService.validate_tenant_access(db, token, restaurant_id)
    return KnowledgeRepository.list_by_restaurant(db, restaurant_id)

def service_search_by_document_type(db, token, restaurant_id, doc_type):
    AuthService.validate_tenant_access(db, token, restaurant_id)
    return KnowledgeRepository.search_by_document_type(db, restaurant_id, doc_type)

def service_search_by_title(db, token, restaurant_id, title_query):
    AuthService.validate_tenant_access(db, token, restaurant_id)
    return KnowledgeRepository.search_by_title(db, restaurant_id, title_query)

def service_update_document(db, token, doc_id, update_dict):
    # Retrieve document first
    doc = db.query(KnowledgeDocument).filter(
        KnowledgeDocument.id == doc_id,
        KnowledgeDocument.deleted_at.is_(None)
    ).first()
    if not doc:
        raise ValueError("Document not found")
    # Validate access
    AuthService.validate_tenant_access(db, token, doc.restaurant_id)
    return KnowledgeRepository.update(db, doc_id, update_dict)

def service_delete_document(db, token, doc_id):
    doc = db.query(KnowledgeDocument).filter(
        KnowledgeDocument.id == doc_id,
        KnowledgeDocument.deleted_at.is_(None)
    ).first()
    if not doc:
        return False
    AuthService.validate_tenant_access(db, token, doc.restaurant_id)
    return KnowledgeRepository.soft_delete(db, doc_id)

# =====================================================================
# TEST EXECUTION
# =====================================================================

def run_knowledge_base_tests():
    print("=" * 80)
    print("RUNNING RESTAURANT KNOWLEDGE BASE FOUNDATION VERIFICATION")
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

        # 5. Verify CRUD Operations
        print("\n1. Testing CRUD operations...")

        # Create docs for Restaurant A
        doc_a_menu = service_create_document(
            db, rest_a_token, restaurant_a.id, "Restaurant A Menu", "Appetizers: Garlic Bread, Mains: Pizza", "menu"
        )
        doc_a_faq = service_create_document(
            db, rest_a_token, restaurant_a.id, "Restaurant A FAQ", "Is parking free? Yes.", "faq"
        )
        doc_a_refund = service_create_document(
            db, rest_a_token, restaurant_a.id, "Restaurant A Refund Policy", "Refunds within 5 minutes only.", "refund_policy"
        )

        assert doc_a_menu.id is not None
        assert doc_a_menu.title == "Restaurant A Menu"
        assert doc_a_menu.document_type == "menu"
        print("✓ Knowledge Document creation verified.")

        # Read / Retrieve List
        docs_a = service_list_documents(db, rest_a_token, restaurant_a.id)
        assert len(docs_a) == 3
        print("✓ list_by_restaurant verified.")

        # Search by type
        menu_search = service_search_by_document_type(db, rest_a_token, restaurant_a.id, "menu")
        assert len(menu_search) == 1
        assert menu_search[0].id == doc_a_menu.id
        print("✓ search_by_document_type verified.")

        # Search by title
        title_search = service_search_by_title(db, rest_a_token, restaurant_a.id, "FAQ")
        assert len(title_search) == 1
        assert title_search[0].id == doc_a_faq.id
        print("✓ search_by_title verified.")

        # Update
        updated_doc = service_update_document(
            db, rest_a_token, doc_a_refund.id, {"content": "Updated content: Refunds within 10 minutes."}
        )
        assert updated_doc.content == "Updated content: Refunds within 10 minutes."
        print("✓ update verified.")

        # Soft Delete FAQ
        delete_success = service_delete_document(db, rest_a_token, doc_a_faq.id)
        assert delete_success is True
        
        # Verify it's no longer retrievable
        doc_faq_after = service_get_document(db, rest_a_token, doc_a_faq.id)
        assert doc_faq_after is None
        
        # Verify it physically exists in database with deleted_at timestamp
        raw_doc = db.query(KnowledgeDocument).filter(KnowledgeDocument.id == doc_a_faq.id).first()
        assert raw_doc is not None
        assert raw_doc.deleted_at is not None
        print("✓ soft_delete verified.")

        # 6. Verify Tenant Isolation
        print("\n2. Testing Tenant Isolation boundaries...")
        
        # Create doc for Restaurant B
        doc_b_menu = service_create_document(
            db, rest_b_token, restaurant_b.id, "Restaurant B Menu", "Mains: Pasta, Drinks: Wine", "menu"
        )
        service_create_document(db, rest_b_token, restaurant_b.id, "Restaurant B Delivery", "Within 5 miles limit.", "delivery_policy")
        service_create_document(db, rest_b_token, restaurant_b.id, "Restaurant B Hours", "9 AM to 10 PM daily.", "business_hours")

        # Restaurant A user attempting to read Restaurant B doc -> Blocked
        try:
            service_get_document(db, rest_a_token, doc_b_menu.id)
            assert False, "Failed: Restaurant A user read Restaurant B document"
        except PermissionError as e:
            print(f"✓ Cross-tenant read rejected correctly: {e}")

        # Restaurant A user attempting to list Restaurant B docs -> Blocked
        try:
            service_list_documents(db, rest_a_token, restaurant_b.id)
            assert False, "Failed: Restaurant A user listed Restaurant B documents"
        except PermissionError as e:
            print(f"✓ Cross-tenant list query rejected correctly: {e}")

        # Restaurant A user attempting to delete Restaurant B doc -> Blocked
        try:
            service_delete_document(db, rest_a_token, doc_b_menu.id)
            assert False, "Failed: Restaurant A user deleted Restaurant B document"
        except PermissionError as e:
            print(f"✓ Cross-tenant delete rejected correctly: {e}")

        # 7. Verify Admin Override
        print("\n3. Testing Admin Override features...")
        
        # Admin reading Restaurant A doc -> Allowed
        admin_read = service_get_document(db, admin_token, doc_a_menu.id)
        assert admin_read is not None
        assert admin_read.title == "Restaurant A Menu"

        # Admin listing Restaurant B docs -> Allowed
        admin_list = service_list_documents(db, admin_token, restaurant_b.id)
        assert len(admin_list) == 3
        print("✓ Admin override verified (Admin allowed global access).")

        # 8. Verify Customer Denial
        print("\n4. Testing Customer Access Denials...")
        
        try:
            service_list_documents(db, customer_token, restaurant_a.id)
            assert False, "Failed: Customer was allowed to list documents"
        except PermissionError as e:
            print(f"✓ Customer list attempt rejected: {e}")

        try:
            service_create_document(db, customer_token, restaurant_a.id, "Customer FAQ", "Can I write? No.", "faq")
            assert False, "Failed: Customer was allowed to create documents"
        except PermissionError as e:
            print(f"✓ Customer create attempt rejected: {e}")

        # 9. Verify Active Check Validation
        print("\n5. Testing Inactive & Soft-Deleted restaurant rejections...")
        
        # Deactivate Restaurant B
        restaurant_b.is_active = False
        db.commit()

        # Admin accessing inactive Restaurant B documents -> Rejected with ValueError
        try:
            service_list_documents(db, admin_token, restaurant_b.id)
            assert False, "Failed: Allowed access to inactive restaurant documents"
        except ValueError as e:
            print(f"✓ Inactive restaurant access rejected as expected: {e}")

        # Soft-delete Restaurant A
        RestaurantRepository.soft_delete(db, restaurant_a.id)

        # Admin accessing soft-deleted Restaurant A documents -> Rejected with ValueError
        try:
            service_list_documents(db, admin_token, restaurant_a.id)
            assert False, "Failed: Allowed access to soft-deleted restaurant documents"
        except ValueError as e:
            print(f"✓ Soft-deleted restaurant access rejected as expected: {e}")

        # Verify that Restaurant A documents are NOT cascade-deleted (deleted_at is still None)
        raw_doc_a_menu = db.query(KnowledgeDocument).filter(KnowledgeDocument.id == doc_a_menu.id).first()
        assert raw_doc_a_menu is not None
        assert raw_doc_a_menu.deleted_at is None
        print("✓ No soft-delete cascade verified (documents retained for future restoration).")

    finally:
        db.close()
        # Clean up database file
        if os.path.exists(test_db_path):
            os.remove(test_db_path)

    print("\n✓ ALL RESTAURANT KNOWLEDGE BASE FOUNDATION VERIFICATION TESTS PASSED SUCCESSFULLY!")
    print("=" * 80)
    sys.exit(0)

if __name__ == "__main__":
    run_knowledge_base_tests()
