import os
import sys
import shutil
from unittest import mock

# Ensure project root is in the path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.append(project_root)

# Force a distinct test DB for validation
test_db_path = os.path.join(project_root, "data", "test_kb_rag_orchestration.db")
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
from backend.rag.retriever import retrieve_relevant_chunks_with_metadata
from backend.rag.prompt_builder import build_rag_prompt
from backend.rag.rag_service import RAGService

def run_rag_orchestration_tests():
    print("=" * 80)
    print("RUNNING RESTAURANT RAG ORCHESTRATION VERIFICATION")
    print("=" * 80)

    # 1. Initialize test database
    print("Initializing test database tables...")
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    created_restaurants = []

    try:
        # 2. Create test restaurants
        print("\nCreating active test restaurants...")
        restaurant_a = RestaurantRepository.create(db, name="Restaurant Alpha")
        restaurant_b = RestaurantRepository.create(db, name="Restaurant Beta")
        created_restaurants.extend([restaurant_a.id, restaurant_b.id])

        # 3. Create test users & tokens to add documents
        print("Creating test users & tokens...")
        rest_a_user = UserRepository.create(
            db, "rest_a@saas.com", "pass1234", UserRole.RESTAURANT, restaurant_id=restaurant_a.id
        )
        rest_b_user = UserRepository.create(
            db, "rest_b@saas.com", "pass1234", UserRole.RESTAURANT, restaurant_id=restaurant_b.id
        )
        rest_a_token = AuthService.create_access_token(rest_a_user.id, rest_a_user.email, rest_a_user.role.value)
        rest_b_token = AuthService.create_access_token(rest_b_user.id, rest_b_user.email, rest_b_user.role.value)

        # Clear vector stores to start fresh
        for rest_id in created_restaurants:
            p_dir = os.path.join(project_root, "data", "chroma_db", rest_id)
            if os.path.exists(p_dir):
                shutil.rmtree(p_dir)

        # Create document for Restaurant Alpha
        print("Adding knowledge document to Restaurant Alpha...")
        doc_a = KnowledgeService.create_document(
            db=db,
            token=rest_a_token,
            restaurant_id=restaurant_a.id,
            title="Alpha Hours",
            content="We are open from 8 AM to 10 PM on weekdays and 9 AM to 11 PM on weekends.",
            document_type="business_hours"
        )

        # =====================================================================
        # TEST 1: Retrieval Metadata
        # =====================================================================
        print("\n1. Testing Retrieval Metadata...")
        chunks = retrieve_relevant_chunks_with_metadata(restaurant_a.id, "open hours")
        assert len(chunks) > 0, "Failed to retrieve chunks for Restaurant Alpha"
        first_chunk = chunks[0]
        
        # Verify required keys in returned metadata objects
        assert "content" in first_chunk, "Metadata missing 'content' key"
        assert "document_id" in first_chunk, "Metadata missing 'document_id' key"
        assert "title" in first_chunk, "Metadata missing 'title' key"
        assert "document_type" in first_chunk, "Metadata missing 'document_type' key"
        assert first_chunk["document_id"] == str(doc_a.id)
        assert first_chunk["title"] == "Alpha Hours"
        assert first_chunk["document_type"] == "business_hours"
        print("✓ Retrieval metadata keys validated successfully.")

        # Test empty KB returns empty list
        empty_chunks = retrieve_relevant_chunks_with_metadata(restaurant_b.id, "nonexistent query")
        assert empty_chunks == [], f"Expected empty list for Restaurant Beta, got {empty_chunks}"
        print("✓ Empty knowledge base returns empty list.")

        # =====================================================================
        # TEST 2: Prompt Builder
        # =====================================================================
        print("\n2. Testing Prompt Builder...")
        test_chunks = [{
            "content": "This is pizza recipe context.",
            "document_id": "123-abc",
            "title": "Pizza Recipe",
            "document_type": "menu"
        }]
        prompt = build_rag_prompt("Restaurant Alpha", test_chunks, "What is the secret recipe?")
        
        # Verify prompt sections are correctly constructed
        assert "Restaurant Alpha" in prompt, "Prompt missing restaurant name"
        assert "This is pizza recipe context." in prompt, "Prompt missing context chunks"
        assert "What is the secret recipe?" in prompt, "Prompt missing user question"
        assert "Only answer using the provided knowledge" in prompt, "Prompt missing hallucination-prevention instructions"
        assert "I could not find that information in the restaurant knowledge base." in prompt, "Prompt missing fallback directions"
        print("✓ Prompt builder sections validated successfully.")

        # =====================================================================
        # TEST 3: RAG Service (CRUD, Rejections, and Empty fallbacks)
        # =====================================================================
        print("\n3. Testing RAG Service...")
        
        # 3a. Successful generation (real or mocked)
        # To avoid calling the API directly during test automation if keys are not set,
        # we can mock GenerativeModel.generate_content. Let's write a mock.
        mock_response = mock.MagicMock()
        mock_response.text = "We are open from 8 AM to 10 PM on weekdays."
        
        with mock.patch("google.generativeai.GenerativeModel.generate_content", return_value=mock_response):
            res = RAGService.answer_question(db, restaurant_a.id, "What are your business hours?")
            assert res["answer"] == "We are open from 8 AM to 10 PM on weekdays."
            assert len(res["sources"]) == 1
            assert res["sources"][0]["title"] == "Alpha Hours"
            assert res["chunks_used"] == len(chunks)
            print("✓ RAG Service successfully answered question.")

        # 3b. Empty KB Fallback (Gemini is bypassed)
        res_empty = RAGService.answer_question(db, restaurant_b.id, "What is your refund policy?")
        assert res_empty["answer"] == "I could not find that information in the restaurant knowledge base."
        assert res_empty["sources"] == []
        assert res_empty["chunks_used"] == 0
        print("✓ Empty knowledge base fallback handled without calling Gemini.")

        # 3c. Missing Restaurant Rejection
        try:
            RAGService.answer_question(db, "00000000-0000-0000-0000-000000000000", "hello")
            assert False, "Failed to reject non-existent restaurant"
        except ValueError as e:
            assert "Restaurant is inactive or deleted" in str(e)
            print("✓ Missing restaurant rejection threw ValueError as expected.")

        # 3d. Soft-deleted Restaurant Rejection
        soft_deleted_rest = RestaurantRepository.create(db, name="Restaurant Gamma")
        created_restaurants.append(soft_deleted_rest.id)
        # Soft-delete the restaurant
        RestaurantRepository.soft_delete(db, soft_deleted_rest.id)
        try:
            RAGService.answer_question(db, soft_deleted_rest.id, "hello")
            assert False, "Failed to reject soft-deleted restaurant"
        except ValueError as e:
            assert "Restaurant is inactive or deleted" in str(e)
            print("✓ Soft-deleted restaurant rejection threw ValueError as expected.")

        # =====================================================================
        # TEST 4: Tenant Isolation
        # =====================================================================
        print("\n4. Testing Tenant Isolation...")
        doc_b = KnowledgeService.create_document(
            db=db,
            token=rest_b_token,
            restaurant_id=restaurant_b.id,
            title="Beta Secret Sauce",
            content="Beta secret sauce consists of honey mustard and cayenne pepper.",
            document_type="menu"
        )
        
        # Query on Restaurant Alpha for Beta content
        chunks_a_query_b = retrieve_relevant_chunks_with_metadata(restaurant_a.id, "honey mustard cayenne pepper")
        # Should not find B's content
        for c in chunks_a_query_b:
            assert c["title"] != "Beta Secret Sauce", "Tenant boundary breach: Restaurant A retrieved Restaurant B content!"
        print("✓ Tenant isolation in retrieval validated successfully.")

        # =====================================================================
        # TEST 5: Source Attribution & Deduplication
        # =====================================================================
        print("\n5. Testing Source Attribution & Deduplication...")
        # Mock retriever to return duplicate chunks for the same document
        mock_retrieved_chunks = [
            {
                "content": "First paragraph of hours.",
                "document_id": "doc-uuid-1",
                "title": "Alpha Hours Document",
                "document_type": "business_hours"
            },
            {
                "content": "Second paragraph of hours.",
                "document_id": "doc-uuid-1",
                "title": "Alpha Hours Document",
                "document_type": "business_hours"
            },
            {
                "content": "Beta pricing info.",
                "document_id": "doc-uuid-2",
                "title": "Menu Document",
                "document_type": "menu"
            }
        ]

        with mock.patch("backend.rag.rag_service.retrieve_relevant_chunks_with_metadata", return_value=mock_retrieved_chunks):
            with mock.patch("google.generativeai.GenerativeModel.generate_content", return_value=mock_response):
                res_dedup = RAGService.answer_question(db, restaurant_a.id, "What are the timings?")
                # Expected sources should only contain 2 unique items
                assert len(res_dedup["sources"]) == 2
                doc_ids = [s["document_id"] for s in res_dedup["sources"]]
                assert "doc-uuid-1" in doc_ids
                assert "doc-uuid-2" in doc_ids
                assert res_dedup["chunks_used"] == 3
                print("✓ Source deduplication and correct attribution verified.")

        # =====================================================================
        # TEST 6: Gemini Failure Handling
        # =====================================================================
        print("\n6. Testing Gemini Failure Handling...")
        # Mock generate_content to throw exception (e.g. Quota/Connection error)
        with mock.patch("google.generativeai.GenerativeModel.generate_content", side_effect=RuntimeError("API Quota Exceeded")):
            res_fail = RAGService.answer_question(db, restaurant_a.id, "What are your hours?")
            assert res_fail["error"] is True
            assert res_fail["answer"] == "The knowledge assistant is temporarily unavailable."
            assert res_fail["sources"] == []
            assert res_fail["chunks_used"] == 0
            print("✓ Gemini exception handled gracefully inside RAG Service (no escape).")

    finally:
        db.close()
        # Clean up database files and folder
        if os.path.exists(test_db_path):
            os.remove(test_db_path)
        for rest_id in created_restaurants:
            p_dir = os.path.join(project_root, "data", "chroma_db", rest_id)
            if os.path.exists(p_dir):
                shutil.rmtree(p_dir)

    print("\n✓ ALL RAG ORCHESTRATION VERIFICATION TESTS PASSED SUCCESSFULLY!")
    print("=" * 80)
    sys.exit(0)

if __name__ == "__main__":
    run_rag_orchestration_tests()
