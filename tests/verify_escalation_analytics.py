import os
import sys
import unittest.mock as mock

# Ensure project root is in path
current_file_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_file_dir)
if project_root not in sys.path:
    sys.path.append(project_root)

# Setup isolated test database path
test_db_path = os.path.join(project_root, "data", "test_escalation_analytics.db")
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
from backend.analytics.event_logger import create_event
from backend.analytics.session_analytics import reset_session_analytics, get_session_analytics

class MockResponse:
    def __init__(self, text):
        self.text = text

def mock_generate_content(*args, **kwargs):
    return MockResponse("This is a mock response from Pizza Paradise support.")

def run_analytics_tests():
    print("=" * 80)
    print("RUNNING ESCALATION ANALYTICS INTEGRATION VERIFICATION")
    print("=" * 80)

    # 1. Reset session analytics to start with a clean state
    reset_session_analytics()
    
    # Check that initial state is clean
    stats = get_session_analytics()
    assert stats["total_queries"] == 0
    assert stats["escalation_count"] == 0
    assert stats["escalation_rate"] == 0.0
    assert stats["escalation_reason_distribution"] == {}

    # Mock the GenerativeModel.generate_content call
    with mock.patch("google.generativeai.generative_models.GenerativeModel.generate_content", side_effect=mock_generate_content):
        
        # Test Case 1: Normal Query (No Escalation)
        query_normal = "What is the price of the Margherita pizza?"
        print(f"\n[1] Running normal query: '{query_normal}'")
        res_normal = generate_response(query_normal, return_dict=True)
        assert res_normal["escalation"]["escalate"] is False
        assert res_normal["escalation"]["reason"] == "No Escalation Required"
        
        # Verify stats after 1 query
        stats = get_session_analytics()
        assert stats["total_queries"] == 1
        assert stats["escalation_count"] == 0
        assert stats["escalation_rate"] == 0.0
        assert stats["escalation_reason_distribution"] == {"No Escalation Required": 1}
        print("    Status -> ✓ Passed")

        # Test Case 2: Refund Request Query (Escalation)
        query_refund = "Can I get a refund for my late cold pizza?"
        print(f"\n[2] Running refund query: '{query_refund}'")
        res_refund = generate_response(query_refund, return_dict=True)
        assert res_refund["escalation"]["escalate"] is True
        assert res_refund["escalation"]["reason"] in ["Refund Request", "Customer Complaint"]
        reason_refund = res_refund["escalation"]["reason"]

        # Verify stats after 2 queries
        stats = get_session_analytics()
        assert stats["total_queries"] == 2
        assert stats["escalation_count"] == 1
        assert abs(stats["escalation_rate"] - 0.5) < 1e-6
        assert stats["escalation_reason_distribution"] == {
            "No Escalation Required": 1,
            reason_refund: 1
        }
        print("    Status -> ✓ Passed")

        # Test Case 3: Human Assistance Keyword (Escalation)
        query_human = "I need to talk to a manager or support agent"
        print(f"\n[3] Running human assistance query: '{query_human}'")
        res_human = generate_response(query_human, return_dict=True)
        assert res_human["escalation"]["escalate"] is True
        assert res_human["escalation"]["reason"] == "Human Assistance Requested"

        # Verify stats after 3 queries
        stats = get_session_analytics()
        assert stats["total_queries"] == 3
        assert stats["escalation_count"] == 2
        assert abs(stats["escalation_rate"] - (2.0 / 3.0)) < 1e-6
        assert stats["escalation_reason_distribution"] == {
            "No Escalation Required": 1,
            reason_refund: 1,
            "Human Assistance Requested": 1
        }
        print("    Status -> ✓ Passed")

        # Test Case 4: Low Confidence (Escalation)
        # Mock classify_intent to return confidence = 0.5 (which triggers low confidence escalation)
        print("\n[4] Running low confidence query (mocked)")
        mock_intent = {
            "intent": "Menu Inquiry",
            "confidence": 0.50,
            "layer": "Rule-Based"
        }
        with mock.patch("backend.gemini_service.classify_intent", return_value=mock_intent):
            res_low_conf = generate_response("What toppings do you have?", return_dict=True)
            assert res_low_conf["escalation"]["escalate"] is True
            assert res_low_conf["escalation"]["reason"] == "Low Confidence"

        # Verify stats after 4 queries
        stats = get_session_analytics()
        assert stats["total_queries"] == 4
        assert stats["escalation_count"] == 3
        assert abs(stats["escalation_rate"] - 0.75) < 1e-6
        assert stats["escalation_reason_distribution"] == {
            "No Escalation Required": 1,
            reason_refund: 1,
            "Human Assistance Requested": 1,
            "Low Confidence": 1
        }
        print("    Status -> ✓ Passed")

        # Test Case 5: Legacy Compatibility Verification
        print("\n[5] Verifying legacy compatibility fallback defaults")
        legacy_event_input = {
            "timestamp": "2026-06-09T18:00:00",
            "restaurant_id": "Restaurant_A",
            "query": "Hello",
            "intent": "General Greeting",
            "intent_confidence": 0.99,
            "intent_layer": "Rule-Based",
            "best_similarity_score": 0.80,
            "rag_decision": "FALLBACK",
            "retrieved_sources": [],
            "response_source": "System Fallback",
            "response_length": 50,
            "latency_ms": 12.34
        }
        # Call create_event with the legacy event dictionary (missing escalation fields)
        try:
            validated_event = create_event(legacy_event_input)
            
            # Assertions for injected safe defaults
            assert "event_id" in validated_event, "Event ID not generated"
            assert validated_event["escalated"] is False, "Legacy event escalated should default to False"
            assert validated_event["escalation_reason"] == "No Escalation Required", "Legacy event escalation_reason should default to 'No Escalation Required'"
            
            # Type checks
            assert isinstance(validated_event["escalated"], bool)
            assert isinstance(validated_event["escalation_reason"], str)
            
            print("    Status -> ✓ Passed")
        except Exception as e:
            print(f"    Status -> ✗ Failed: Legacy event validation threw exception: {e}")
            sys.exit(1)

    print("\n" + "=" * 80)
    print("✓ ALL ESCALATION ANALYTICS TESTS PASSED")
    print("=" * 80)

if __name__ == "__main__":
    run_analytics_tests()
