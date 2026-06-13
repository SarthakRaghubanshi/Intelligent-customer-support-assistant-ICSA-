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
    print("RUNNING BUSINESS INTELLIGENCE & RANKING VERIFICATION")
    print("=" * 80)

    # 1. Reset all stats
    reset_session_analytics()

    # 2. Simulate traffic matching our target dataset
    events = [
        # Restaurant_A: 2 queries, 0 escalations, confidence: 0.90 and 0.80 (avg 0.85), latency: 100.0 and 200.0 (avg 150.0)
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
        # Restaurant_B: 3 queries, 1 escalation, confidence: 0.70, 0.80, 0.90 (avg 0.80), latency: 150.0, 150.0, 300.0 (avg 200.0)
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
        # Restaurant_C: 1 query, 0 escalations, confidence: 0.90 (avg 0.90), latency: 100.0 (avg 100.0)
        {
            "timestamp": "2026-06-13T10:00:06",
            "restaurant_id": "Restaurant_C",
            "query": "C query 1",
            "intent": "Delivery Inquiry",
            "intent_confidence": 0.90,
            "intent_layer": "Rule-Based",
            "best_similarity_score": 0.84,
            "rag_decision": "PASS_TO_GEMINI",
            "response_source": "Gemini",
            "response_length": 65,
            "latency_ms": 100.0,
            "escalated": False,
            "escalation_reason": "No Escalation Required"
        }
    ]

    print("Processing mock events...")
    for ev in events:
        update_session_analytics(ev)

    all_stats = get_all_tenant_analytics()
    active_tenants = [tid for tid in all_stats.keys() if all_stats[tid].get("total_queries", 0) > 0]

    # Verify active tenants
    assert set(active_tenants) == {"Restaurant_A", "Restaurant_B", "Restaurant_C"}

    # 3. Perform identical Ranking Sort priorities:
    # 1. Lowest escalation rate (asc)
    # 2. Highest confidence score (desc)
    # 3. Highest query volume (desc)
    ranked_tenants = sorted(
        active_tenants,
        key=lambda tid: (
            all_stats[tid].get("escalation_rate", 0.0),
            -all_stats[tid].get("average_confidence_score", 0.0),
            -all_stats[tid].get("total_queries", 0)
        )
    )

    print("\n--- Verifying Ranking Order ---")
    print("Ranked Order:", ranked_tenants)
    assert ranked_tenants[0] == "Restaurant_C", f"Expected Rank 1 to be Restaurant_C, got {ranked_tenants[0]}"
    assert ranked_tenants[1] == "Restaurant_A", f"Expected Rank 2 to be Restaurant_A, got {ranked_tenants[1]}"
    assert ranked_tenants[2] == "Restaurant_B", f"Expected Rank 3 to be Restaurant_B, got {ranked_tenants[2]}"
    print("✓ Ranking order verified (tie breaker correctly used confidence score).")

    # 4. Verify Leader Metrics
    # Top Performer
    top_performer = ranked_tenants[0]
    assert top_performer == "Restaurant_C"
    
    # Traffic Leader
    traffic_leader = max(active_tenants, key=lambda tid: all_stats[tid].get("total_queries", 0))
    assert traffic_leader == "Restaurant_B"

    # Escalation Leader
    escalation_leader = max(active_tenants, key=lambda tid: all_stats[tid].get("escalation_count", 0))
    assert escalation_leader == "Restaurant_B"

    # Fastest Response
    fastest_restaurant = min(active_tenants, key=lambda tid: all_stats[tid].get("average_latency_ms", 0.0))
    assert fastest_restaurant == "Restaurant_C"

    print("\n--- Verifying Operational Leaders ---")
    print("🏆 Top Performer:", top_performer)
    print("🚦 Traffic Leader:", traffic_leader)
    print("🚨 Most Escalated:", escalation_leader)
    print("⚡ Fastest Response:", fastest_restaurant)
    print("✓ Operational leaders verified successfully.")

    # 5. Query Share Calculations
    global_total = sum(all_stats[t].get("total_queries", 0) for t in active_tenants)
    assert global_total == 6

    share_a = all_stats["Restaurant_A"].get("total_queries", 0) / global_total
    share_b = all_stats["Restaurant_B"].get("total_queries", 0) / global_total
    share_c = all_stats["Restaurant_C"].get("total_queries", 0) / global_total

    print("\n--- Verifying Query Share Percentages ---")
    print(f"Restaurant_A Share: {share_a * 100:.1f}%")
    print(f"Restaurant_B Share: {share_b * 100:.1f}%")
    print(f"Restaurant_C Share: {share_c * 100:.1f}%")

    assert abs(share_a - (2/6)) < 1e-6
    assert abs(share_b - (3/6)) < 1e-6
    assert abs(share_c - (1/6)) < 1e-6
    print("✓ Query share calculations correct.")

    print("\n✓ ALL BUSINESS INTELLIGENCE VERIFICATION TESTS PASSED SUCCESSFULLY!")
    print("=" * 80)
    sys.exit(0)

if __name__ == "__main__":
    run_verification()
