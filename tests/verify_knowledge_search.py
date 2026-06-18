import os
import sys
import shutil

# Ensure project root is in the path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.append(project_root)

# Force a distinct test DB for validation
test_db_path = os.path.join(project_root, "data", "test_kb_search_saas.db")
os.environ["DATABASE_URL"] = f"sqlite:///{test_db_path}"

# Clean test db file if it already exists
if os.path.exists(test_db_path):
    os.remove(test_db_path)

from backend.database.database import engine, Base, SessionLocal
from tests.utils import test_bootstrap
from backend.models.user import User, UserRole
from backend.repositories.restaurant_repository import RestaurantRepository
from backend.repositories.user_repository import UserRepository
from backend.services.auth_service import AuthService
from backend.services.knowledge_service import KnowledgeService
from backend.rag.retriever import retrieve_relevant_chunks

def run_knowledge_search_tests():
    print("=" * 80)
    print("RUNNING RESTAURANT KNOWLEDGE SEARCH & RETRIEVAL VERIFICATION")
    print("=" * 80)

    # 1. Initialize test database
    print("Initializing test database tables...")
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    # Track folders we need to clean up
    created_restaurants = []

    try:
        # 2. Create test restaurants
        print("\nCreating active test restaurants...")
        restaurant_a = RestaurantRepository.create(db, name="Restaurant Alpha")
        restaurant_b = RestaurantRepository.create(db, name="Restaurant Beta")
        created_restaurants.extend([restaurant_a.id, restaurant_b.id])

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

        # Ensure vector store starts empty for both restaurants
        for rest_id in created_restaurants:
            p_dir = os.path.join(project_root, "data", "chroma_db", rest_id)
            if os.path.exists(p_dir):
                shutil.rmtree(p_dir)

        # =====================================================================
        # TEST 1: Graceful Empty State Handling
        # =====================================================================
        print("\n1. Testing Graceful Empty State Handling...")
        results = retrieve_relevant_chunks("What is your refund policy?", restaurant_a.id)
        assert results == [], f"Expected empty list for non-existent collection, got {results}"
        print("✓ Graceful empty state retrieval verified.")

        # =====================================================================
        # TEST 2: Real-time Creation Sync
        # =====================================================================
        print("\n2. Testing Real-time Creation Sync...")
        doc_a = KnowledgeService.create_document(
            db=db,
            token=rest_a_token,
            restaurant_id=restaurant_a.id,
            title="Restaurant Alpha Crust Recipe",
            content="Our pizza dough is proofed for 48 hours and we top it with fresh mozzarella cheese and olive oil.",
            document_type="menu"
        )
        
        # Retrieve chunks
        print("Retrieving chunks from vector store...")
        results_a = retrieve_relevant_chunks("mozzarella cheese proofed", restaurant_a.id, k=1)
        assert len(results_a) > 0, "Failed: Vector store did not sync newly created document."
        best_match = results_a[0]
        assert "mozzarella cheese" in best_match["content"]
        assert best_match["restaurant_id"] == restaurant_a.id
        assert best_match["source"] == "Restaurant Alpha Crust Recipe"
        print("✓ Dynamic document creation index synced successfully.")

        # =====================================================================
        # TEST 3: Tenant Containment / Isolation
        # =====================================================================
        print("\n3. Testing Tenant Containment / Isolation in RAG retrieval...")
        doc_b = KnowledgeService.create_document(
            db=db,
            token=rest_b_token,
            restaurant_id=restaurant_b.id,
            title="Restaurant Beta Burger Secret",
            content="Our special sauce is made of kewpie mayo, sweet pickle relish, and a dash of cayenne pepper.",
            document_type="menu"
        )

        # Search Beta queries on Alpha
        results_a_search_b = retrieve_relevant_chunks("kewpie mayo and relish", restaurant_a.id)
        # Should not find Beta's document chunks
        assert len(results_a_search_b) == 0 or all(restaurant_a.id == r["restaurant_id"] for r in results_a_search_b)
        
        # Search Alpha queries on Beta
        results_b_search_a = retrieve_relevant_chunks("proofed dough recipe", restaurant_b.id)
        assert len(results_b_search_a) == 0 or all(restaurant_b.id == r["restaurant_id"] for r in results_b_search_a)
        print("✓ Tenant containment in search and retrieval successfully verified.")

        # =====================================================================
        # TEST 4: Real-time Update Propagation
        # =====================================================================
        print("\n4. Testing Real-time Update Propagation...")
        KnowledgeService.update_document(
            db=db,
            token=rest_a_token,
            doc_id=doc_a.id,
            update_dict={
                "content": "Our pizza dough is strictly GLUTEN-FREE and we use plant-based vegan cheddar cheese."
            }
        )

        # Query updated content
        results_updated = retrieve_relevant_chunks("gluten-free plant-based vegan cheddar", restaurant_a.id, k=1)
        assert len(results_updated) > 0
        assert "gluten-free" in results_updated[0]["content"].lower()
        assert "vegan cheddar" in results_updated[0]["content"].lower()

        # Query old content -> should not match well (old chunks removed)
        results_old = retrieve_relevant_chunks("proofed fresh mozzarella", restaurant_a.id)
        # Verify the top match does not contain mozzarella (or if it does, it's not the old document content)
        if results_old:
            assert "mozzarella" not in results_old[0]["content"], "Failed: Old document chunks were not deleted from Chroma."
        print("✓ Dynamic update sync verified successfully.")

        # =====================================================================
        # TEST 5: Real-time Soft-delete Propagation
        # =====================================================================
        print("\n5. Testing Real-time Soft-delete Propagation...")
        KnowledgeService.delete_document(db=db, token=rest_a_token, doc_id=doc_a.id)

        # Retrieve again -> should not return the document
        results_after_delete = retrieve_relevant_chunks("gluten-free plant-based", restaurant_a.id)
        assert len(results_after_delete) == 0, f"Expected 0 chunks, got {len(results_after_delete)}"
        print("✓ Soft-delete vector synchronization verified successfully.")

        # =====================================================================
        # TEST 6: Full Rebuild Sync
        # =====================================================================
        print("\n6. Testing Full Rebuild / Sync method...")
        # Create a document for Restaurant Alpha again (will be dynamic)
        doc_a_new = KnowledgeService.create_document(
            db=db,
            token=rest_a_token,
            restaurant_id=restaurant_a.id,
            title="Alpha Hours",
            content="We are open from 8 AM to 10 PM on weekdays.",
            document_type="business_hours"
        )
        
        # Verify it retrieved
        res1 = retrieve_relevant_chunks("open hours", restaurant_a.id, k=1)
        assert len(res1) > 0
        
        # Delete document from vector store directly to simulate a desync
        from backend.rag.vector_store import delete_document_from_vector_store
        delete_document_from_vector_store(restaurant_a.id, doc_a_new.id)
        
        # Retrieval should fail gracefully / return empty
        res2 = retrieve_relevant_chunks("open hours", restaurant_a.id)
        assert len(res2) == 0
        
        # Trigger rebuild
        print("Triggering full rebuild for Restaurant Alpha...")
        KnowledgeService.rebuild_vector_store(db, admin_token, restaurant_a.id)
        
        # Retrieval should work again
        res3 = retrieve_relevant_chunks("open hours", restaurant_a.id, k=1)
        assert len(res3) > 0
        assert "8 AM to 10 PM" in res3[0]["content"]
        print("✓ Manual vector store rebuild utility verified successfully.")

    finally:
        db.close()
        # Clean up databases and generated Chroma test folders
        if os.path.exists(test_db_path):
            os.remove(test_db_path)
        
        for rest_id in created_restaurants:
            p_dir = os.path.join(project_root, "data", "chroma_db", rest_id)
            if os.path.exists(p_dir):
                shutil.rmtree(p_dir)

    print("\n✓ ALL RESTAURANT KNOWLEDGE SEARCH & RETRIEVAL VERIFICATION TESTS PASSED SUCCESSFULLY!")
    print("=" * 80)
    sys.exit(0)

if __name__ == "__main__":
    run_knowledge_search_tests()
