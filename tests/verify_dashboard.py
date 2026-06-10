import os
import sys

# Ensure project root is in path
current_file_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_file_dir)
if project_root not in sys.path:
    sys.path.append(project_root)

# 1. Assert successful imports
try:
    from backend.analytics.session_analytics import get_session_analytics
    from frontend.components.dashboard import render_dashboard
    print("✓ Successfully imported dashboard rendering and backend analytics components.")
except Exception as e:
    print(f"❌ Import Failure: {e}")
    sys.exit(1)

# 2. Retrieve session metrics and assert required contract keys
try:
    stats = get_session_analytics()
    required_keys = {
        "total_queries",
        "intent_distribution",
        "sentiment_distribution",
        "language_distribution",
        "fallback_count",
        "gemini_count",
        "escalation_count",
        "escalation_rate",
        "average_latency_ms",
        "average_similarity_score"
    }
    
    missing_keys = required_keys - set(stats.keys())
    if missing_keys:
        print(f"❌ Session metrics contract is missing keys: {missing_keys}")
        sys.exit(1)
        
    # Check types for a few key properties
    assert isinstance(stats["total_queries"], int), "total_queries must be an int"
    assert isinstance(stats["intent_distribution"], dict), "intent_distribution must be a dict"
    assert isinstance(stats["sentiment_distribution"], dict), "sentiment_distribution must be a dict"
    assert isinstance(stats["language_distribution"], dict), "language_distribution must be a dict"
    assert isinstance(stats["fallback_count"], int), "fallback_count must be an int"
    assert isinstance(stats["gemini_count"], int), "gemini_count must be an int"
    assert isinstance(stats["escalation_count"], int), "escalation_count must be an int"
    assert isinstance(stats["escalation_rate"], (int, float)), "escalation_rate must be numeric"
    assert isinstance(stats["average_latency_ms"], (int, float)), "average_latency_ms must be numeric"
    assert isinstance(stats["average_similarity_score"], (int, float)), "average_similarity_score must be numeric"
    
    print("✓ Session analytics dictionary contains all required contract keys with correct types.")
    print("=" * 80)
    print("✓ DASHBOARD BACKEND METRICS CONTRACT PASSED")
    print("=" * 80)
    sys.exit(0)
except Exception as e:
    print(f"❌ Verification Failure: {e}")
    sys.exit(1)
