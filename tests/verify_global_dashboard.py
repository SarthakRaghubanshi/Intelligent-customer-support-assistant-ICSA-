import os
import sys

# Ensure project root is in path
current_file_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_file_dir)
if project_root not in sys.path:
    sys.path.append(project_root)

from backend.analytics.session_analytics import reset_session_analytics, update_session_analytics, get_session_analytics

def run_verification():
    print("=" * 80)
    print("RUNNING GLOBAL ANALYTICS DASHBOARD VERIFICATION")
    print("=" * 80)

    # 1. Reset all session analytics to clear any previous state
    reset_session_analytics()

    # Define mock events for Restaurant_A, Restaurant_B, and Restaurant_C
    events = [
        # Restaurant_A: 2 queries
        {
            "timestamp": "2026-06-13T10:00:01",
            "restaurant_id": "Restaurant_A",
            "query": "A query 1",
            "intent": "Menu Inquiry",
            "intent_confidence": 0.95,
            "intent_layer": "Rule-Based",
            "best_similarity_score": 0.85,
            "rag_decision": "PASS_TO_GEMINI",
            "response_source": "Gemini",
            "response_length": 40,
            "latency_ms": 150.0,
            "escalated": False,
            "escalation_reason": "No Escalation Required"
        },
        {
            "timestamp": "2026-06-13T10:00:02",
            "restaurant_id": "Restaurant_A",
            "query": "A query 2",
            "intent": "Delivery Inquiry",
            "intent_confidence": 0.90,
            "intent_layer": "Rule-Based",
            "best_similarity_score": 0.80,
            "rag_decision": "PASS_TO_GEMINI",
            "response_source": "Gemini",
            "response_length": 45,
            "latency_ms": 160.0,
            "escalated": False,
            "escalation_reason": "No Escalation Required"
        },
        # Restaurant_B: 3 queries
        {
            "timestamp": "2026-06-13T10:00:03",
            "restaurant_id": "Restaurant_B",
            "query": "B query 1",
            "intent": "Complaint",
            "intent_confidence": 0.85,
            "intent_layer": "Rule-Based",
            "best_similarity_score": 0.75,
            "rag_decision": "PASS_TO_GEMINI",
            "response_source": "Gemini",
            "response_length": 50,
            "latency_ms": 170.0,
            "escalated": True,
            "escalation_reason": "Customer Complaint"
        },
        {
            "timestamp": "2026-06-13T10:00:04",
            "restaurant_id": "Restaurant_B",
            "query": "B query 2",
            "intent": "Menu Inquiry",
            "intent_confidence": 0.80,
            "intent_layer": "Rule-Based",
            "best_similarity_score": 0.70,
            "rag_decision": "PASS_TO_GEMINI",
            "response_source": "Gemini",
            "response_length": 55,
            "latency_ms": 180.0,
            "escalated": False,
            "escalation_reason": "No Escalation Required"
        },
        {
            "timestamp": "2026-06-13T10:00:05",
            "restaurant_id": "Restaurant_B",
            "query": "B query 3",
            "intent": "Hours Inquiry",
            "intent_confidence": 0.75,
            "intent_layer": "Rule-Based",
            "best_similarity_score": 0.65,
            "rag_decision": "PASS_TO_GEMINI",
            "response_source": "Gemini",
            "response_length": 60,
            "latency_ms": 190.0,
            "escalated": False,
            "escalation_reason": "No Escalation Required"
        },
        # Restaurant_C: 1 query
        {
            "timestamp": "2026-06-13T10:00:06",
            "restaurant_id": "Restaurant_C",
            "query": "C query 1",
            "intent": "Delivery Inquiry",
            "intent_confidence": 0.90,
            "intent_layer": "Rule-Based",
            "best_similarity_score": 0.88,
            "rag_decision": "PASS_TO_GEMINI",
            "response_source": "Gemini",
            "response_length": 65,
            "latency_ms": 200.0,
            "escalated": False,
            "escalation_reason": "No Escalation Required"
        }
    ]

    # Process all events
    print("Simulating queries across restaurants...")
    for ev in events:
        update_session_analytics(ev)

    print("\n--- Analytics Results Verification ---")
    
    # Fetch data as the dashboard would:
    # Specific restaurants:
    stats_a = get_session_analytics("Restaurant_A")
    stats_b = get_session_analytics("Restaurant_B")
    stats_c = get_session_analytics("Restaurant_C")
    # "All Restaurants" maps to get_session_analytics(None)
    stats_all = get_session_analytics(None)

    count_a = stats_a.get("total_queries", 0)
    count_b = stats_b.get("total_queries", 0)
    count_c = stats_c.get("total_queries", 0)
    count_all = stats_all.get("total_queries", 0)

    print(f"Restaurant_A dashboard -> {count_a}")
    print(f"Restaurant_B dashboard -> {count_b}")
    print(f"Restaurant_C dashboard -> {count_c}")
    print(f"All Restaurants -> {count_all}")

    # Assertions
    assert count_a == 2, f"Expected Restaurant_A total queries to be 2, got {count_a}"
    assert count_b == 3, f"Expected Restaurant_B total queries to be 3, got {count_b}"
    assert count_c == 1, f"Expected Restaurant_C total queries to be 1, got {count_c}"
    assert count_all == 6, f"Expected All Restaurants total queries to be 6, got {count_all}"

    print("\n✓ Verification Successful: Metrics aggregate correctly across all levels!")
    print("=" * 80)
    sys.exit(0)

if __name__ == "__main__":
    run_verification()
