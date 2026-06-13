import os
import sys

# Ensure project root is in path
current_file_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_file_dir)
if project_root not in sys.path:
    sys.path.append(project_root)

from backend.analytics.session_analytics import (
    reset_session_analytics, 
    update_session_analytics, 
    get_all_tenant_analytics
)

def run_verification():
    print("=" * 80)
    print("RUNNING ADMIN COMPARISON ANALYTICS VERIFICATION")
    print("=" * 80)

    # 1. Reset all stats
    reset_session_analytics()

    # 2. Assert that it is empty initially
    initial_all_stats = get_all_tenant_analytics()
    assert len(initial_all_stats) == 0, f"Expected 0 active tenants initially, got {len(initial_all_stats)}"
    print("✓ Initialized empty database state successfully.")

    # 3. Simulate traffic across 3 tenants
    events = [
        # Restaurant_A: 2 queries
        {
            "timestamp": "2026-06-13T10:00:01",
            "restaurant_id": "Restaurant_A",
            "query": "A query 1",
            "intent": "Menu Inquiry",
            "intent_confidence": 0.90,
            "intent_layer": "Rule-Based",
            "best_similarity_score": 0.80,
            "rag_decision": "PASS_TO_GEMINI",
            "response_source": "Gemini",
            "response_length": 40,
            "latency_ms": 100.0,
            "escalated": False,
            "escalation_reason": "No Escalation Required"
        },
        {
            "timestamp": "2026-06-13T10:00:02",
            "restaurant_id": "Restaurant_A",
            "query": "A query 2",
            "intent": "Delivery Inquiry",
            "intent_confidence": 0.80,
            "intent_layer": "Rule-Based",
            "best_similarity_score": 0.70,
            "rag_decision": "PASS_TO_GEMINI",
            "response_source": "Gemini",
            "response_length": 45,
            "latency_ms": 200.0,
            "escalated": False,
            "escalation_reason": "No Escalation Required"
        },
        # Restaurant_B: 3 queries (1 escalated)
        {
            "timestamp": "2026-06-13T10:00:03",
            "restaurant_id": "Restaurant_B",
            "query": "B query 1",
            "intent": "Complaint",
            "intent_confidence": 0.70,
            "intent_layer": "Rule-Based",
            "best_similarity_score": 0.60,
            "rag_decision": "PASS_TO_GEMINI",
            "response_source": "Gemini",
            "response_length": 50,
            "latency_ms": 150.0,
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
            "latency_ms": 150.0,
            "escalated": False,
            "escalation_reason": "No Escalation Required"
        },
        {
            "timestamp": "2026-06-13T10:00:05",
            "restaurant_id": "Restaurant_B",
            "query": "B query 3",
            "intent": "Hours Inquiry",
            "intent_confidence": 0.90,
            "intent_layer": "Rule-Based",
            "best_similarity_score": 0.80,
            "rag_decision": "PASS_TO_GEMINI",
            "response_source": "Gemini",
            "response_length": 60,
            "latency_ms": 300.0,
            "escalated": False,
            "escalation_reason": "No Escalation Required"
        },
        # Restaurant_C: 1 query
        {
            "timestamp": "2026-06-13T10:00:06",
            "restaurant_id": "Restaurant_C",
            "query": "C query 1",
            "intent": "Delivery Inquiry",
            "intent_confidence": 0.88,
            "intent_layer": "Rule-Based",
            "best_similarity_score": 0.84,
            "rag_decision": "PASS_TO_GEMINI",
            "response_source": "Gemini",
            "response_length": 65,
            "latency_ms": 400.0,
            "escalated": False,
            "escalation_reason": "No Escalation Required"
        }
    ]

    print("Simulating event processing...")
    for ev in events:
        update_session_analytics(ev)

    # 4. Retrieve all tenant stats
    all_stats = get_all_tenant_analytics()

    print("\n--- Verifying active tenants mapping ---")
    assert set(all_stats.keys()) == {"Restaurant_A", "Restaurant_B", "Restaurant_C"}, \
        f"Expected keys to be {{'Restaurant_A', 'Restaurant_B', 'Restaurant_C'}}, got {set(all_stats.keys())}"
    print("✓ Active tenants correct.")

    # 5. Check no internal accumulator fields are exposed
    for tenant, data in all_stats.items():
        for k in data.keys():
            assert not k.startswith("_"), f"Internal accumulator field '{k}' exposed in tenant '{tenant}'!"
    print("✓ Internal accumulator fields correctly excluded.")

    # 6. Verify Restaurant_A stats details
    stats_a = all_stats["Restaurant_A"]
    assert stats_a["total_queries"] == 2
    assert abs(stats_a["average_latency_ms"] - 150.0) < 1e-6
    assert abs(stats_a["average_confidence_score"] - 0.85) < 1e-6
    assert abs(stats_a["average_similarity_score"] - 0.75) < 1e-6
    assert stats_a["escalation_count"] == 0
    assert abs(stats_a["escalation_rate"] - 0.0) < 1e-6
    print("✓ Restaurant_A metrics calculations correct.")

    # 7. Verify Restaurant_B stats details
    stats_b = all_stats["Restaurant_B"]
    assert stats_b["total_queries"] == 3
    assert abs(stats_b["average_latency_ms"] - 200.0) < 1e-6
    assert abs(stats_b["average_confidence_score"] - 0.80) < 1e-6
    assert abs(stats_b["average_similarity_score"] - 0.70) < 1e-6
    assert stats_b["escalation_count"] == 1
    assert abs(stats_b["escalation_rate"] - (1/3)) < 1e-6
    print("✓ Restaurant_B metrics calculations correct.")

    # 8. Verify Restaurant_C stats details
    stats_c = all_stats["Restaurant_C"]
    assert stats_c["total_queries"] == 1
    assert abs(stats_c["average_latency_ms"] - 400.0) < 1e-6
    assert abs(stats_c["average_confidence_score"] - 0.88) < 1e-6
    assert abs(stats_c["average_similarity_score"] - 0.84) < 1e-6
    assert stats_c["escalation_count"] == 0
    assert abs(stats_c["escalation_rate"] - 0.0) < 1e-6
    print("✓ Restaurant_C metrics calculations correct.")

    print("\n✓ ALL ADMIN COMPARISON VERIFICATION TESTS PASSED SUCCESSFULLY!")
    print("=" * 80)
    sys.exit(0)

if __name__ == "__main__":
    run_verification()
