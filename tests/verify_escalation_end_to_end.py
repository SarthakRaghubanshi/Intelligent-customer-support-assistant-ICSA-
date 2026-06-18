import os
import sys
import unittest.mock as mock

# Ensure project root is in path
current_file_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_file_dir)
if project_root not in sys.path:
    sys.path.append(project_root)

# Setup isolated test database path
test_db_path = os.path.join(project_root, "data", "test_escalation_end_to_end.db")
os.environ["DATABASE_URL"] = f"sqlite:///{test_db_path}"

# Clean test db file if it already exists
if os.path.exists(test_db_path):
    try:
        os.remove(test_db_path)
    except Exception:
        pass

from tests.utils.test_bootstrap import bootstrap_test_database, bootstrap_default_test_data

# Bootstrap the test database and seed Restaurant_A
SessionLocalTest = bootstrap_test_database(os.environ["DATABASE_URL"])
db = SessionLocalTest()
try:
    bootstrap_default_test_data(db)
finally:
    db.close()

from backend.gemini_service import generate_response
from backend.analytics.session_analytics import reset_session_analytics, get_session_analytics

class MockResponse:
    def __init__(self, text):
        self.text = text

def mock_generate_content(*args, **kwargs):
    return MockResponse("This is a mock response from Pizza Paradise support.")

def run_end_to_end_tests():
    print("=" * 80)
    print("RUNNING SYSTEM-LEVEL END-TO-END ESCALATION TESTS")
    print("=" * 80)

    # Reset analytics before tests
    reset_session_analytics()
    
    passed_all = True

    try:
        # We patch GenerativeModel.generate_content to prevent live API calls during verification
        with mock.patch("google.generativeai.generative_models.GenerativeModel.generate_content", side_effect=mock_generate_content):
            
            # -------------------------------------------------------------
            # Test Case 1: Standard Pipeline Flow & Structured Response Contract
            # -------------------------------------------------------------
            print("\n[1] Testing Case 1: Standard Pipeline Flow with return_dict=True")
            query_normal = "What is the price of the Margherita Royale?"
            res_normal = generate_response(query_normal, return_dict=True)
            
            print(f"    Returned Type: {type(res_normal).__name__}")
            print(f"    Response payload: {res_normal}")
            
            # Assert structured response contract
            assert isinstance(res_normal, dict), "Case 1 Failed: Expected response to be a dictionary."
            
            EXPECTED_KEYS = {
                "response",
                "language",
                "intent",
                "sentiment",
                "confidence",
                "escalation"
            }
            assert set(res_normal.keys()) == EXPECTED_KEYS, f"Case 1 Failed: Response keys do not match contract. Got {set(res_normal.keys())}"
            
            # Assert correct escalation metadata
            escalation_payload = res_normal["escalation"]
            assert escalation_payload["escalate"] is False, "Expected escalate=False for standard query."
            assert escalation_payload["reason"] == "No Escalation Required", f"Unexpected reason: {escalation_payload['reason']}"
            
            print("    Status -> ✓ Case 1 Passed")

            # -------------------------------------------------------------
            # Test Case 2: Fallback + Escalation Coexistence
            # -------------------------------------------------------------
            print("\n[2] Testing Case 2: Fallback + Escalation Coexistence")
            query_fallback_esc = "I demand to speak to a manager about a completely different restaurant."
            
            # Mock retrieve_relevant_chunks to return empty list, forcing RAG threshold fallback
            # Mock retrieve_relevant_chunks_with_metadata to return empty list, forcing RAG threshold fallback
            with mock.patch("backend.rag.rag_service.retrieve_relevant_chunks_with_metadata", return_value=[]):
                res_fallback_esc = generate_response(query_fallback_esc, return_dict=True)
            
            print(f"    Returned Type: {type(res_fallback_esc).__name__}")
            print(f"    Response payload: {res_fallback_esc}")
            
            # Assert structured response contract
            assert isinstance(res_fallback_esc, dict), "Case 2 Failed: Expected response to be a dictionary."
            assert set(res_fallback_esc.keys()) == EXPECTED_KEYS, f"Case 2 Failed: Response keys do not match contract."
            
            # Assert fallback response coexists with escalation
            expected_fallback = "I could not find that information in the restaurant knowledge base."
            assert res_fallback_esc["response"] == expected_fallback, f"Expected fallback response, got: {res_fallback_esc['response']}"
            
            # Assert escalation triggered
            assert res_fallback_esc["escalation"]["escalate"] is True, "Expected escalate=True due to manager keyword."
            assert res_fallback_esc["escalation"]["reason"] == "Human Assistance Requested", f"Expected 'Human Assistance Requested', got: {res_fallback_esc['escalation']['reason']}"
            
            print("    Status -> ✓ Case 2 Passed")

            # -------------------------------------------------------------
            # Test Case 3: Analytics Consistency
            # -------------------------------------------------------------
            print("\n[3] Testing Case 3: Analytics Consistency Verification")
            stats = get_session_analytics()
            print(f"    Current Session Analytics Stats: {stats}")
            
            assert stats["total_queries"] == 2, f"Expected total_queries=2, got: {stats['total_queries']}"
            assert stats["escalation_count"] == 1, f"Expected escalation_count=1, got: {stats['escalation_count']}"
            assert abs(stats["escalation_rate"] - 0.5) < 1e-6, f"Expected escalation_rate=0.5, got: {stats['escalation_rate']}"
            assert stats["fallback_count"] == 1, f"Expected fallback_count=1, got: {stats['fallback_count']}"
            assert stats["gemini_count"] == 1, f"Expected gemini_count=1, got: {stats['gemini_count']}"
            
            expected_reason_dist = {
                "No Escalation Required": 1,
                "Human Assistance Requested": 1
            }
            assert stats["escalation_reason_distribution"] == expected_reason_dist, f"Expected reason distribution {expected_reason_dist}, got: {stats['escalation_reason_distribution']}"
            
            print("    Status -> ✓ Case 3 Passed")

            # -------------------------------------------------------------
            # Test Case 4: Backward Compatibility Contract
            # -------------------------------------------------------------
            print("\n[4] Testing Case 4: Backward Compatibility Contract (return_dict=False)")
            query_compat = "What are your hours?"
            res_compat = generate_response(query_compat, return_dict=False)
            
            print(f"    Returned Type: {type(res_compat).__name__}")
            print(f"    Response value: '{res_compat}'")
            
            assert isinstance(res_compat, str), "Case 4 Failed: Expected response to be a string."
            assert len(res_compat) > 0, "Case 4 Failed: Expected non-empty response."
            
            print("    Status -> ✓ Case 4 Passed")

    except AssertionError as e:
        print(f"\n❌ TEST SUITE FAILED: {str(e)}")
        passed_all = False
    except Exception as e:
        print(f"\n❌ TEST SUITE ENCOUNTERED EXCEPTION: {str(e)}")
        passed_all = False
    finally:
        if os.path.exists(test_db_path):
            try:
                os.remove(test_db_path)
            except Exception:
                pass

    print("\n" + "=" * 80)
    if passed_all:
        print("✓ ALL SYSTEM-LEVEL END-TO-END ESCALATION TESTS PASSED")
        print("=" * 80)
        sys.exit(0)
    else:
        print("✗ SOME SYSTEM-LEVEL END-TO-END ESCALATION TESTS FAILED")
        print("=" * 80)
        sys.exit(1)

if __name__ == "__main__":
    run_end_to_end_tests()
