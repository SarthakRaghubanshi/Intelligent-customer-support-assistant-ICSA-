import os
import sys
import unittest.mock as mock

# Ensure project root is in the Python path
current_file_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_file_dir)
if project_root not in sys.path:
    sys.path.append(project_root)

# Setup isolated test database path
test_db_path = os.path.join(project_root, "data", "test_pipeline_integration.db")
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

# Helper MockResponse class
class MockResponse:
    def __init__(self, text):
        self.text = text

# Mock content generation function mapping prompt inputs to predictable responses
def mock_generate_content(*args, **kwargs):
    prompt = ""
    for arg in args:
        if isinstance(arg, str):
            prompt = arg
            break
    if not prompt:
        prompt = kwargs.get("contents", "")
        if not isinstance(prompt, str):
            prompt = str(prompt)
            
    prompt_lower = prompt.lower()
    
    # 1. Intent Classification Prompt
    if "intent classification engine" in prompt_lower:
        if "gravity" in prompt_lower:
            return MockResponse('{"intent": "Out Of Scope", "confidence": 0.98}')
        elif "refund" in prompt_lower or "cold" in prompt_lower:
            return MockResponse('{"intent": "Refund Inquiry", "confidence": 0.95}')
        else:
            return MockResponse('{"intent": "Delivery Inquiry", "confidence": 0.95}')
            
    # 2. Sentiment Classification Prompt
    elif "sentiment classification engine" in prompt_lower:
        if "refund" in prompt_lower or "cold" in prompt_lower or "late" in prompt_lower:
            return MockResponse('{"sentiment": "Negative", "confidence": 0.95}')
        else:
            return MockResponse('{"sentiment": "Neutral", "confidence": 0.90}')
            
    # 3. Language Detection Prompt
    elif "language detection engine" in prompt_lower:
        return MockResponse('{"language": "English", "code": "en", "confidence": 0.99}')
        
    # 4. Response Generation Prompt (Grounded in context)
    else:
        if "delivery" in prompt_lower:
            return MockResponse("The delivery charge is ₹50 within Zone 1, and ₹100 for Zone 2.")
        else:
            return MockResponse("This is a mock grounded response from Pizza Paradise support.")

def run_pipeline_verification():
    print("=" * 80)
    print("RUNNING E2E PIPELINE INTEGRATION VERIFICATION")
    print("=" * 80)

    # Initialize results reporting list
    results = []

    # Reset analytics state for clean tests
    reset_session_analytics()

    try:
        # We patch the live GenerativeModel.generate_content call to ensure test determinism
        with mock.patch("google.generativeai.generative_models.GenerativeModel.generate_content", side_effect=mock_generate_content):
            
            # ----------------------------------------------------------------------
            # SCENARIO A: FAQ Query (Delivery charges query with RAG hit)
            # ----------------------------------------------------------------------
            print("\n[SCENARIO A] Testing FAQ Query: 'What are your delivery charges?'")
            try:
                res_a = generate_response("What are your delivery charges?", return_dict=True)
                print(f"    Returned Payload: {res_a}")

                # Assertions
                assert isinstance(res_a, dict), "Result must be a dictionary."
                assert res_a["intent"] == "Delivery Inquiry", f"Expected 'Delivery Inquiry' intent, got '{res_a['intent']}'"
                assert res_a["sentiment"] == "Neutral", f"Expected 'Neutral' sentiment, got '{res_a['sentiment']}'"
                assert "delivery" in res_a["response"].lower() or "charge" in res_a["response"].lower(), "Expected grounded Gemini response content."
                assert res_a["escalation"]["escalate"] is False, "Expected escalate=False for standard FAQ."
                
                # Check analytics logging
                stats = get_session_analytics()
                assert stats["total_queries"] == 1, f"Expected total_queries = 1, got {stats['total_queries']}"
                assert len(stats["recent_events"]) == 1, "Expected recent_events list to contain 1 record."
                assert stats["recent_events"][0]["query"] == "What are your delivery charges?"
                assert stats["recent_events"][0]["rag_decision"] == "PASS_TO_GEMINI", "Expected RAG to be utilized."
                
                results.append(("Scenario A: FAQ Query", "PASS"))
                print("    Status -> ✓ Scenario A Passed")
            except Exception as e:
                results.append(("Scenario A: FAQ Query", f"FAIL: {str(e)}"))
                print(f"    Status -> ✗ Scenario A Failed: {str(e)}")

            # ----------------------------------------------------------------------
            # SCENARIO B: Complaint / Refund Query (Negative sentiment, Complaint intent)
            # ----------------------------------------------------------------------
            print("\n[SCENARIO B] Testing Complaint Query: 'My order arrived cold and late. I want a refund.'")
            try:
                res_b = generate_response("My order arrived cold and late. I want a refund.", return_dict=True)
                print(f"    Returned Payload: {res_b}")

                # Assertions
                assert isinstance(res_b, dict), "Result must be a dictionary."
                assert res_b["intent"] in ["Refund Inquiry", "Complaint"], f"Expected Complaint/Refund intent, got '{res_b['intent']}'"
                assert res_b["sentiment"] == "Negative", f"Expected 'Negative' sentiment, got '{res_b['sentiment']}'"
                assert res_b["escalation"]["escalate"] is True, "Expected escalate=True for negative complaint."
                
                # Check analytics logging
                stats = get_session_analytics()
                assert stats["total_queries"] == 2, f"Expected total_queries = 2, got {stats['total_queries']}"
                assert stats["escalation_count"] == 1, f"Expected escalation_count = 1, got {stats['escalation_count']}"
                assert stats["recent_events"][1]["escalated"] is True
                
                results.append(("Scenario B: Complaint / Refund Query", "PASS"))
                print("    Status -> ✓ Scenario B Passed")
            except Exception as e:
                results.append(("Scenario B: Complaint / Refund Query", f"FAIL: {str(e)}"))
                print(f"    Status -> ✗ Scenario B Failed: {str(e)}")

            # ----------------------------------------------------------------------
            # SCENARIO C: Out-of-Scope Query (Fallback trigger)
            # ----------------------------------------------------------------------
            print("\n[SCENARIO C] Testing Out-of-Scope Query: 'What is the speed of gravity?'")
            try:
                res_c = generate_response("What is the speed of gravity?", return_dict=True)
                print(f"    Returned Payload: {res_c}")

                # Assertions
                assert isinstance(res_c, dict), "Result must be a dictionary."
                assert res_c["response"] == "I could not find that information in the restaurant knowledge base.", "Expected RAG fallback text."
                
                # Check analytics logging
                stats = get_session_analytics()
                assert stats["total_queries"] == 3, f"Expected total_queries = 3, got {stats['total_queries']}"
                assert stats["fallback_count"] == 1, f"Expected fallback_count = 1, got {stats['fallback_count']}"
                assert stats["recent_events"][2]["rag_decision"] == "FALLBACK", "Expected decision to be FALLBACK."
                
                results.append(("Scenario C: Out-of-Scope Query", "PASS"))
                print("    Status -> ✓ Scenario C Passed")
            except Exception as e:
                results.append(("Scenario C: Out-of-Scope Query", f"FAIL: {str(e)}"))
                print(f"    Status -> ✗ Scenario C Failed: {str(e)}")

        # ----------------------------------------------------------------------
        # PRINT RESULTS SUMMARY
        # ----------------------------------------------------------------------
        print("\n" + "=" * 80)
        print("INTEGRATION VERIFICATION SUMMARY")
        print("=" * 80)
        failed = False
        for test_name, status in results:
            print(f" - {test_name:<40} : {status}")
            if "FAIL" in status:
                failed = True
                
        print("=" * 80)
        if failed:
            print("✗ E2E PIPELINE INTEGRATION VERIFICATION FAILED")
            print("=" * 80)
            sys.exit(1)
        else:
            print("✓ ALL E2E PIPELINE INTEGRATION VERIFICATION TESTS PASSED")
            print("=" * 80)
            sys.exit(0)
    finally:
        # Clean up database files and folder
        if os.path.exists(test_db_path):
            try:
                os.remove(test_db_path)
            except Exception:
                pass

if __name__ == "__main__":
    run_pipeline_verification()
