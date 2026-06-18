import os
import sys
import unittest.mock as mock

# Ensure project root is in path
current_file_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_file_dir)
if project_root not in sys.path:
    sys.path.append(project_root)

# Setup isolated test database path
test_db_path = os.path.join(project_root, "data", "test_escalation_integration.db")
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

class MockResponse:
    def __init__(self, text):
        self.text = text

def mock_generate_content(*args, **kwargs):
    return MockResponse("This is a mock response from Pizza Paradise support.")

def run_integration_tests():
    print("=" * 80)
    print("RUNNING PIPELINE ESCALATION INTEGRATION VERIFICATION")
    print("=" * 80)

    try:
        # We patch GenerativeModel.generate_content to prevent live API calls during verification
        with mock.patch("google.generativeai.generative_models.GenerativeModel.generate_content", side_effect=mock_generate_content):
            
            # Test Case 1: Standard query (no escalation trigger, return_dict=True)
            query_normal = "What is the price of the Margherita pizza?"
            print(f"\n[1] Testing normal query with return_dict=True: '{query_normal}'")
            res_normal = generate_response(query_normal, return_dict=True)
            
            print(f"    Returned Type: {type(res_normal).__name__}")
            print(f"    Response dict: {res_normal}")
            
            assert isinstance(res_normal, dict), "Test 1 Failed: Expected response to be a dictionary."
            assert "response" in res_normal, "Missing 'response' in result."
            assert isinstance(res_normal["language"], dict), "Expected 'language' to be a dictionary."
            assert "language" in res_normal["language"], "Missing 'language' key inside language metadata."
            assert "code" in res_normal["language"], "Missing 'code' key inside language metadata."
            assert "confidence" in res_normal["language"], "Missing 'confidence' key inside language metadata."
            assert "layer" in res_normal["language"], "Missing 'layer' key inside language metadata."
            assert "intent" in res_normal, "Missing 'intent' in result."
            assert "sentiment" in res_normal, "Missing 'sentiment' in result."
            assert "confidence" in res_normal, "Missing 'confidence' in result."
            assert "escalation" in res_normal, "Missing 'escalation' in result."
            
            escalation_payload = res_normal["escalation"]
            assert escalation_payload["escalate"] is False, "Expected escalate=False for standard query."
            assert escalation_payload["reason"] == "No Escalation Required", f"Unexpected reason: {escalation_payload['reason']}"
            print("    Status -> ✓ Test 1 Passed")
            
            # Test Case 2: Escalation query (Refund Inquiry, return_dict=True)
            query_esc = "Can I get a refund for my late cold pizza?"
            print(f"\n[2] Testing escalation query with return_dict=True: '{query_esc}'")
            res_esc = generate_response(query_esc, return_dict=True)
            
            print(f"    Returned Type: {type(res_esc).__name__}")
            print(f"    Response dict: {res_esc}")
            
            assert isinstance(res_esc, dict), "Test 2 Failed: Expected response to be a dictionary."
            assert res_esc["escalation"]["escalate"] is True, "Expected escalate=True."
            assert res_esc["escalation"]["reason"] in ["Refund Request", "Customer Complaint", "Negative Sentiment"], f"Unexpected reason: {res_esc['escalation']['reason']}"
            print("    Status -> ✓ Test 2 Passed")

            # Test Case 3: Keyword Escalation query (Human Keyword, return_dict=True)
            query_kw = "I want to speak to a manager or staff representative"
            print(f"\n[3] Testing keyword query with return_dict=True: '{query_kw}'")
            res_kw = generate_response(query_kw, return_dict=True)
            
            print(f"    Returned Type: {type(res_kw).__name__}")
            print(f"    Response dict: {res_kw}")
            
            assert isinstance(res_kw, dict), "Test 3 Failed: Expected response to be a dictionary."
            assert res_kw["escalation"]["escalate"] is True, "Expected escalate=True."
            assert res_kw["escalation"]["reason"] == "Human Assistance Requested", f"Unexpected reason: {res_kw['escalation']['reason']}"
            print("    Status -> ✓ Test 3 Passed")

            # Test Case 4: Default call compatibility (return_dict=False)
            print(f"\n[4] Testing backward compatibility call: '{query_normal}'")
            res_str = generate_response(query_normal)
            
            print(f"    Returned Type: {type(res_str).__name__}")
            print(f"    Response value: '{res_str}'")
            
            assert isinstance(res_str, str), "Test 4 Failed: Expected string response."
            print("    Status -> ✓ Test 4 Passed")

        print("\n" + "=" * 80)
        print("✓ ALL INTEGRATION VERIFICATION TESTS PASSED")
        print("=" * 80)
    finally:
        # Clean up database files and folder
        if os.path.exists(test_db_path):
            try:
                os.remove(test_db_path)
            except Exception:
                pass

if __name__ == "__main__":
    run_integration_tests()
