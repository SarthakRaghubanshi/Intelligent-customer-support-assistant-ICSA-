import os
import sys
import unittest.mock as mock
from datetime import datetime

# Ensure project root is in path
current_file_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_file_dir)
if project_root not in sys.path:
    sys.path.append(project_root)

# Setup isolated test database path
test_db_path = os.path.join(project_root, "data", "test_ai_pipeline_integration.db")
os.environ["DATABASE_URL"] = f"sqlite:///{test_db_path}"

# Clean test db file if it already exists
if os.path.exists(test_db_path):
    try:
        os.remove(test_db_path)
    except Exception:
        pass

from tests.utils.test_bootstrap import bootstrap_test_database, bootstrap_restaurant
SessionLocalTest = bootstrap_test_database(os.environ["DATABASE_URL"])
from backend.services.conversation_orchestrator import ConversationOrchestrator
from backend.analytics.session_analytics import reset_session_analytics, get_session_analytics

class MockResponse:
    def __init__(self, text):
        self.text = text

def mock_generate_content(*args, **kwargs):
    return MockResponse("This is a mock response from our unified support AI.")

def run_orchestrator_tests():
    print("=" * 80)
    print("RUNNING STEP 8 UNIFIED AI ORCHESTRATION PIPELINE TESTS")
    print("=" * 80)

    # Initialize test database
    db = SessionLocalTest()
    reset_session_analytics()

    try:
        # 1. Create a test restaurant
        restaurant = bootstrap_restaurant(db, "Pizza_Test_Bed_ID", "Pizza Test Bed")
        
        # 2. Setup mock patches
        with mock.patch("google.generativeai.generative_models.GenerativeModel.generate_content", side_effect=mock_generate_content):
            
            # --- TEST CASE 1: Standard FAQ message routing to RAG and single Gemini invocation ---
            print("\n[TEST 1] Standard FAQ query...")
            query = "What is the price of the Margherita pizza?"
            
            # Since there are no context documents loaded in vector db, similarity search will yield no matches,
            # so it fallback-triggers normally. We patch retriever to simulate a valid RAG hit.
            mock_chunks = [{
                "content": "Margherita Royale costs ₹299 for personal and ₹499 for medium.",
                "document_id": "doc-999",
                "title": "Pizza Menu",
                "document_type": "menu",
                "score": 0.50 # Under 0.75 threshold
            }]
            
            with mock.patch("backend.rag.rag_service.retrieve_relevant_chunks_with_metadata", return_value=mock_chunks):
                # Mock vector store similarity search to attach score
                with mock.patch("backend.rag.vector_store.load_vector_store") as mock_load:
                    mock_store = mock.MagicMock()
                    mock_store.similarity_search_with_score.return_value = [(mock.MagicMock(), 0.50)]
                    mock_load.return_value = mock_store
                    
                    res = ConversationOrchestrator.orchestrate(
                        db=db,
                        restaurant_id=restaurant.id,
                        question=query
                    )
            
            print(f"Result payload: {res}")
            
            # Assert schema contract
            assert isinstance(res, dict), "Result must be a dict"
            assert "answer" in res
            assert "intent" in res
            assert "sentiment" in res
            assert "language" in res
            assert "language_code" in res
            assert "escalation_result" in res
            assert "sources" in res
            assert "chunks_used" in res
            assert "prompt" in res
            
            assert res["intent"] == "Menu Inquiry"
            assert res["sentiment"] == "Neutral"
            assert res["language"] == "English"
            assert res["language_code"] == "en"
            assert res["chunks_used"] == 1
            assert len(res["sources"]) == 1
            assert res["sources"][0]["document_id"] == "doc-999"
            assert res["sources"][0]["snippet"] == mock_chunks[0]["content"]
            assert res["escalation_result"]["escalate"] is False
            print("✓ [TEST 1] Standard FAQ routing passed successfully.")

            # --- TEST CASE 2: Escalation message validation ---
            print("\n[TEST 2] Escalation query...")
            esc_query = "Can I get a refund? My pizza was cold."
            
            # Setup mock chunks
            esc_chunks = [{
                "content": "Refunds are processed within 2 hours.",
                "document_id": "doc-888",
                "title": "Refund Policy",
                "document_type": "refund_policy",
                "score": 0.30
            }]
            
            with mock.patch("backend.rag.rag_service.retrieve_relevant_chunks_with_metadata", return_value=esc_chunks):
                with mock.patch("backend.rag.vector_store.load_vector_store") as mock_load:
                    mock_store = mock.MagicMock()
                    mock_store.similarity_search_with_score.return_value = [(mock.MagicMock(), 0.30)]
                    mock_load.return_value = mock_store
                    
                    res_esc = ConversationOrchestrator.orchestrate(
                        db=db,
                        restaurant_id=restaurant.id,
                        question=esc_query
                    )
            
            print(f"Result payload: {res_esc}")
            assert res_esc["escalation_result"]["escalate"] is True
            assert res_esc["intent"] in ["Refund Inquiry", "Complaint"]
            assert res_esc["sentiment"] == "Negative"
            print("✓ [TEST 2] Escalation routing passed successfully.")

            # --- TEST CASE 3: Analytics verification ---
            print("\n[TEST 3] Analytics verification...")
            stats = get_session_analytics()
            print(f"Current Stats: {stats}")
            assert stats["total_queries"] == 2
            assert stats["escalation_count"] == 1
            print("✓ [TEST 3] Analytics verification passed successfully.")

    finally:
        db.close()
        # Clean up database files and folder
        if os.path.exists(test_db_path):
            try:
                os.remove(test_db_path)
            except Exception:
                pass

    print("\n✓ ALL UNIFIED AI ORCHESTRATION PIPELINE INTEGRATION TESTS PASSED SUCCESSFULLY!")
    print("=" * 80)
    sys.exit(0)

if __name__ == "__main__":
    run_orchestrator_tests()
