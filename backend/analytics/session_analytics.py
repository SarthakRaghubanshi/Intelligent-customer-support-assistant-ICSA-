from typing import Dict, Any

# In-memory session stats store
_stats = {
    "total_queries": 0,
    "intent_distribution": {},
    "fallback_count": 0,
    "gemini_count": 0,
    
    # Internal accumulators for accurate running average calculations
    "_total_latency_ms": 0.0,
    "_total_similarity_score": 0.0,
    
    "average_latency_ms": 0.0,
    "average_similarity_score": 0.0
}

def update_session_analytics(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Updates the in-memory session statistics with a new AnalyticsEvent.
    Prints the aggregated session metrics to standard output with the prefix [SESSION_LOG].
    
    Args:
        event (Dict[str, Any]): The validated AnalyticsEvent dict containing 13 fields.
        
    Returns:
        Dict[str, Any]: A copy of the updated session statistics (excluding internal accumulator fields).
    """
    # Extract values safely
    intent = event.get("intent", "Unknown")
    response_source = event.get("response_source", "")
    latency_ms = event.get("latency_ms", 0.0)
    best_similarity_score = event.get("best_similarity_score", 1.0)

    # 1. Update total queries count
    _stats["total_queries"] += 1

    # 2. Update intent distribution
    _stats["intent_distribution"][intent] = _stats["intent_distribution"].get(intent, 0) + 1

    # 3. Update response counts
    if response_source == "Gemini":
        _stats["gemini_count"] += 1
    elif response_source == "System Fallback":
        _stats["fallback_count"] += 1

    # 4. Update running averages using internal accumulators
    _stats["_total_latency_ms"] += float(latency_ms)
    _stats["_total_similarity_score"] += float(best_similarity_score)

    _stats["average_latency_ms"] = _stats["_total_latency_ms"] / _stats["total_queries"]
    _stats["average_similarity_score"] = _stats["_total_similarity_score"] / _stats["total_queries"]

    # 5. Print updated metrics
    print(f"\n=================== [SESSION_LOG] ===================")
    print(f"Total Queries:            {_stats['total_queries']}")
    print(f"Intent Distribution:      {_stats['intent_distribution']}")
    print(f"Fallback Count:           {_stats['fallback_count']}")
    print(f"Gemini Count:             {_stats['gemini_count']}")
    print(f"Average Latency:          {_stats['average_latency_ms']:.2f} ms")
    print(f"Average Similarity Score: {_stats['average_similarity_score']:.4f}")
    print(f"======================================================\n")

    return get_session_analytics()

def get_session_analytics() -> Dict[str, Any]:
    """
    Returns a copy of the current in-memory session statistics,
    filtering out internal accumulator fields starting with an underscore.
    """
    return {k: (dict(v) if isinstance(v, dict) else v) for k, v in _stats.items() if not k.startswith("_")}

def reset_session_analytics() -> None:
    """
    Resets all metrics and accumulators back to default.
    """
    _stats["total_queries"] = 0
    _stats["intent_distribution"] = {}
    _stats["fallback_count"] = 0
    _stats["gemini_count"] = 0
    _stats["_total_latency_ms"] = 0.0
    _stats["_total_similarity_score"] = 0.0
    _stats["average_latency_ms"] = 0.0
    _stats["average_similarity_score"] = 0.0
