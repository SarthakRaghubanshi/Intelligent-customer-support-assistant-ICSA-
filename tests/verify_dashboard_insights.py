import os
import sys

# Ensure project root is in path
current_file_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_file_dir)
if project_root not in sys.path:
    sys.path.append(project_root)

from backend.analytics.session_analytics import reset_session_analytics, update_session_analytics, get_session_analytics

def run_insights_verification():
    print("=" * 80)
    print("RUNNING DASHBOARD REPORTING & INSIGHTS CONTRACT TESTS")
    print("=" * 80)

    # 1. Reset and verify initial default values
    reset_session_analytics()
    stats = get_session_analytics()
    
    print("\n[1] Verifying initial reporting data structures")
    assert "recent_events" in stats, "recent_events key is missing from session stats"
    assert "average_confidence_score" in stats, "average_confidence_score key is missing from session stats"
    assert stats["recent_events"] == [], f"Expected empty recent_events list, got {stats['recent_events']}"
    assert stats["average_confidence_score"] == 0.0, f"Expected initial confidence score to be 0.0, got {stats['average_confidence_score']}"
    print("    Status -> ✓ Initial state passed")

    # 2. Simulate logging distinct query events and verify confidence averaging
    print("\n[2] Verifying confidence score averaging and event history accumulation")
    
    event_1 = {
        "timestamp": "2026-06-10T19:00:01",
        "restaurant_id": "Restaurant_A",
        "query": "What is the price of the Margherita Royale?",
        "intent": "Menu Inquiry",
        "intent_confidence": 0.90,
        "intent_layer": "Rule-Based",
        "best_similarity_score": 0.60,
        "rag_decision": "PASS_TO_GEMINI",
        "response_source": "Gemini",
        "response_length": 50,
        "latency_ms": 120.0,
        "escalated": False,
        "escalation_reason": "No Escalation Required"
    }
    
    event_2 = {
        "timestamp": "2026-06-10T19:00:02",
        "restaurant_id": "Restaurant_A",
        "query": "My pizza is cold and late!",
        "intent": "Complaint",
        "intent_confidence": 0.80,
        "intent_layer": "Rule-Based",
        "best_similarity_score": 0.65,
        "rag_decision": "PASS_TO_GEMINI",
        "response_source": "Gemini",
        "response_length": 45,
        "latency_ms": 110.0,
        "escalated": True,
        "escalation_reason": "Customer Complaint"
    }

    event_3 = {
        "timestamp": "2026-06-10T19:00:03",
        "restaurant_id": "Restaurant_A",
        "query": "I want a refund.",
        "intent": "Refund Inquiry",
        "intent_confidence": 0.70,
        "intent_layer": "Rule-Based",
        "best_similarity_score": 0.50,
        "rag_decision": "PASS_TO_GEMINI",
        "response_source": "Gemini",
        "response_length": 60,
        "latency_ms": 130.0,
        "escalated": True,
        "escalation_reason": "Refund Request"
    }

    # Process events one-by-one
    update_session_analytics(event_1)
    update_session_analytics(event_2)
    update_session_analytics(event_3)
    
    stats = get_session_analytics()
    
    # Assert counts and lists
    assert len(stats["recent_events"]) == 3, f"Expected 3 recent events, got {len(stats['recent_events'])}"
    assert stats["recent_events"][0]["query"] == "What is the price of the Margherita Royale?"
    assert stats["recent_events"][1]["intent"] == "Complaint"
    assert stats["recent_events"][2]["escalation_reason"] == "Refund Request"
    
    # Assert correct math: (0.90 + 0.80 + 0.70) / 3 = 0.80
    expected_confidence = 0.80
    assert abs(stats["average_confidence_score"] - expected_confidence) < 1e-6, f"Expected average confidence to be 0.80, got {stats['average_confidence_score']}"
    
    print("    Status -> ✓ Metrics accumulation and averaging math passed")

    # 3. Verify that the recent events log list is strictly capped at 100 entries
    print("\n[3] Verifying recent_events log capping at 100 records max")
    
    # Log 105 more items
    for i in range(105):
        dummy_event = {
            "timestamp": f"2026-06-10T19:00:{10+i}",
            "restaurant_id": "Restaurant_A",
            "query": f"Query {i}",
            "intent": "Menu Inquiry",
            "intent_confidence": 0.90,
            "intent_layer": "Rule-Based",
            "best_similarity_score": 0.60,
            "rag_decision": "PASS_TO_GEMINI",
            "response_source": "Gemini",
            "response_length": 50,
            "latency_ms": 100.0,
            "escalated": False,
            "escalation_reason": "No Escalation Required"
        }
        update_session_analytics(dummy_event)
        
    stats = get_session_analytics()
    
    # Check capping assertion
    log_length = len(stats["recent_events"])
    assert log_length == 100, f"Expected recent_events history list to be capped at 100, got {log_length}"
    
    # Make sure the oldest events (which were events 1-3 plus some dummy events) were evicted, and the list holds the newest 100 events
    assert stats["recent_events"][-1]["query"] == "Query 104"
    assert stats["recent_events"][0]["query"] != "What is the price of the Margherita Royale?", "Expected oldest event to be evicted"
    
    print("    Status -> ✓ Rolling list capped at 100 successfully")

    print("\n" + "=" * 80)
    print("✓ DASHBOARD INSIGHTS CONTRACT PASSED")
    print("=" * 80)
    sys.exit(0)

if __name__ == "__main__":
    run_insights_verification()
