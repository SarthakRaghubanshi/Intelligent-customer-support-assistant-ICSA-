import os
import sys
import io
from unittest.mock import patch, MagicMock

# Ensure project root is in the path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.append(project_root)

# Force a distinct test DB for validation
test_db_path = os.path.join(project_root, "data", "test_step4_kb_saas.db")
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
from backend.services.auth_service import AuthService
from backend.services.knowledge_service import KnowledgeService

def run_step4_integration_tests():
    print("=" * 80)
    print("RUNNING STEP 4 END-TO-END INTEGRATION TESTS")
    print("=" * 80)

    # 1. Initialize test database
    print("Initializing test database tables...")
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    # Create mock for vector store
    mock_add_vector = MagicMock()

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

        # 5. Patch vector store and test file uploads
        print("\n1. Testing document file upload and database persistence...")
        with patch("backend.rag.vector_store.add_document_to_vector_store", mock_add_vector):
            
            # A. Test TXT file parsing & indexing
            txt_stream = io.BytesIO(b"Hello plain text contents")
            doc_txt = KnowledgeService.upload_document_file(
                db=db,
                token=rest_a_token,
                restaurant_id=restaurant_a.id,
                file_stream=txt_stream,
                filename="doc.txt",
                title="Restaurant FAQ TXT",
                document_type="faq"
            )
            
            assert doc_txt.id is not None
            assert doc_txt.title == "Restaurant FAQ TXT"
            assert doc_txt.content == "Hello plain text contents"
            assert doc_txt.document_type == "faq"
            assert doc_txt.restaurant_id == restaurant_a.id
            
            # Assert vector store sync called
            mock_add_vector.assert_called_with(
                restaurant_id=restaurant_a.id,
                doc_id=doc_txt.id,
                title=doc_txt.title,
                content=doc_txt.content,
                document_type=doc_txt.document_type
            )
            print("✓ Plain text document upload, database save, and vector store integration verified.")

            # B. Verify CSV format mapping and parsing
            csv_stream = io.BytesIO(b"Title,Detail\nMenu 1,Tacos $10\nMenu 2,Burritos $12\n")
            doc_csv = KnowledgeService.upload_document_file(
                db=db,
                token=rest_a_token,
                restaurant_id=restaurant_a.id,
                file_stream=csv_stream,
                filename="menu.csv",
                title="Restaurant Menu CSV",
                document_type="menu"
            )
            
            assert doc_csv.id is not None
            assert "Row 1: Title=Menu 1, Detail=Tacos $10" in doc_csv.content
            assert "Row 2: Title=Menu 2, Detail=Burritos $12" in doc_csv.content
            print("✓ CSV document parsing and mapping verified.")

            # C. Test tenant isolation block during upload
            print("\n2. Testing tenant isolation bounds checking...")
            try:
                # User A tries to upload document to Restaurant B context
                KnowledgeService.upload_document_file(
                    db=db,
                    token=rest_a_token,
                    restaurant_id=restaurant_b.id,
                    file_stream=io.BytesIO(b"should fail"),
                    filename="doc.txt",
                    title="Intruder Doc",
                    document_type="faq"
                )
                assert False, "Failed: Allowed user A to upload files to restaurant B context"
            except PermissionError as err:
                print(f"✓ Correctly rejected cross-tenant upload: {err}")

            # D. Test customer role write denial
            try:
                KnowledgeService.upload_document_file(
                    db=db,
                    token=customer_token,
                    restaurant_id=restaurant_a.id,
                    file_stream=io.BytesIO(b"should fail"),
                    filename="customer.txt",
                    title="Customer Doc",
                    document_type="faq"
                )
                assert False, "Failed: Customer was allowed to upload a file"
            except PermissionError as err:
                print(f"✓ Correctly rejected customer role upload: {err}")

    finally:
        db.close()
        # Clean up database file
        if os.path.exists(test_db_path):
            os.remove(test_db_path)

    print("\n✓ ALL STEP 4 INTEGRATION TESTS PASSED SUCCESSFULLY!")
    print("=" * 80)

if __name__ == "__main__":
    run_step4_integration_tests()
