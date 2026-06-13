from typing import Dict, Any, Optional
import re


# Helper function to create an empty stats template
def _create_empty_stats() -> dict:
    return {
        "total_queries": 0,
        "intent_distribution": {},
        "sentiment_distribution": {},
        "language_distribution": {},
        "fallback_count": 0,
        "gemini_count": 0,
        "escalation_count": 0,
        "escalation_rate": 0.0,
        "escalation_reason_distribution": {},
        "recent_events": [],
        "average_confidence_score": 0.0,
        
        # Internal accumulators for accurate running average calculations
        "_total_latency_ms": 0.0,
        "_total_similarity_score": 0.0,
        "_total_intent_confidence": 0.0,
        
        "average_latency_ms": 0.0,
        "average_similarity_score": 0.0
    }

# In-memory session stats store, keyed by restaurant_id
_stats: Dict[str, Dict[str, Any]] = {}

def _get_tenant_stats(restaurant_id: str) -> dict:
    if restaurant_id not in _stats:
        _stats[restaurant_id] = _create_empty_stats()
    return _stats[restaurant_id]

def update_session_analytics(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Updates the in-memory session statistics with a new AnalyticsEvent.
    Prints the aggregated session metrics to standard output with the prefix [SESSION_LOG].
    
    Args:
        event (Dict[str, Any]): The validated AnalyticsEvent dict containing 13+ fields.
        
    Returns:
        Dict[str, Any]: A copy of the updated session statistics (excluding internal accumulator fields).
    """
    restaurant_id = event.get("restaurant_id", "Restaurant_A")
    t_stats = _get_tenant_stats(restaurant_id)

    # Extract values safely
    intent = event.get("intent", "Unknown")
    sentiment = event.get("sentiment", "Neutral")
    language = event.get("language", "Unknown")
    response_source = event.get("response_source", "")
    latency_ms = event.get("latency_ms", 0.0)
    best_similarity_score = event.get("best_similarity_score", 1.0)
    escalated = event.get("escalated", False)
    escalation_reason = event.get("escalation_reason", "No Escalation Required")

    # 1. Update total queries count
    t_stats["total_queries"] += 1

    # 2. Update intent distribution
    t_stats["intent_distribution"][intent] = t_stats["intent_distribution"].get(intent, 0) + 1

    # Update sentiment and language distributions
    t_stats["sentiment_distribution"][sentiment] = t_stats["sentiment_distribution"].get(sentiment, 0) + 1
    t_stats["language_distribution"][language] = t_stats["language_distribution"].get(language, 0) + 1

    # Update escalation count and reason distribution
    if escalated:
        t_stats["escalation_count"] += 1
    t_stats["escalation_reason_distribution"][escalation_reason] = t_stats["escalation_reason_distribution"].get(escalation_reason, 0) + 1

    # 3. Update response counts
    if response_source == "Gemini":
        t_stats["gemini_count"] += 1
    elif response_source == "System Fallback":
        t_stats["fallback_count"] += 1

    # 4. Update running averages using internal accumulators
    t_stats["_total_latency_ms"] += float(latency_ms)
    t_stats["_total_similarity_score"] += float(best_similarity_score)
    t_stats["_total_intent_confidence"] = t_stats.get("_total_intent_confidence", 0.0) + float(event.get("intent_confidence", 0.0))

    t_stats["average_latency_ms"] = t_stats["_total_latency_ms"] / t_stats["total_queries"]
    t_stats["average_similarity_score"] = t_stats["_total_similarity_score"] / t_stats["total_queries"]
    t_stats["average_confidence_score"] = t_stats["_total_intent_confidence"] / t_stats["total_queries"]
    t_stats["escalation_rate"] = t_stats["escalation_count"] / t_stats["total_queries"]

    # Update recent events list (max 100)
    if "recent_events" not in t_stats:
        t_stats["recent_events"] = []
    t_stats["recent_events"].append(event)
    if len(t_stats["recent_events"]) > 100:
        t_stats["recent_events"] = t_stats["recent_events"][-100:]

    # 5. Print updated metrics
    print(f"\n=================== [SESSION_LOG - {restaurant_id}] ===================")
    print(f"Total Queries:            {t_stats['total_queries']}")
    print(f"Intent Distribution:      {t_stats['intent_distribution']}")
    print(f"Sentiment Distribution:   {t_stats['sentiment_distribution']}")
    print(f"Language Distribution:    {t_stats['language_distribution']}")
    print(f"Fallback Count:           {t_stats['fallback_count']}")
    print(f"Gemini Count:             {t_stats['gemini_count']}")
    print(f"Average Latency:          {t_stats['average_latency_ms']:.2f} ms")
    print(f"Average Similarity Score: {t_stats['average_similarity_score']:.4f}")
    print(f"Average Confidence:       {t_stats['average_confidence_score']:.4f}")
    print(f"Escalation Count:         {t_stats['escalation_count']}")
    print(f"Escalation Rate:          {t_stats['escalation_rate']:.4f}")
    print(f"Escalation Reason Dist:   {t_stats['escalation_reason_distribution']}")
    print(f"======================================================\n")

    return get_session_analytics(restaurant_id)

def _natural_sort_key(event: Dict[str, Any]) -> list:
    ts = event.get("timestamp", "")
    if not isinstance(ts, str):
        ts = str(ts)
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', ts)]

def get_session_analytics(restaurant_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Returns a copy of the current in-memory session statistics,
    filtering out internal accumulator fields starting with an underscore.
    Supports tenant-specific or global aggregates.
    """
    if restaurant_id is None:
        # Compute global aggregate
        global_stats = _create_empty_stats()
        
        for r_id, tenant_stats in _stats.items():
            global_stats["total_queries"] += tenant_stats["total_queries"]
            global_stats["fallback_count"] += tenant_stats["fallback_count"]
            global_stats["gemini_count"] += tenant_stats["gemini_count"]
            global_stats["escalation_count"] += tenant_stats["escalation_count"]
            global_stats["_total_latency_ms"] += tenant_stats["_total_latency_ms"]
            global_stats["_total_similarity_score"] += tenant_stats["_total_similarity_score"]
            global_stats["_total_intent_confidence"] += tenant_stats["_total_intent_confidence"]
            
            # Merge distributions
            for k, v in tenant_stats["intent_distribution"].items():
                global_stats["intent_distribution"][k] = global_stats["intent_distribution"].get(k, 0) + v
            for k, v in tenant_stats["sentiment_distribution"].items():
                global_stats["sentiment_distribution"][k] = global_stats["sentiment_distribution"].get(k, 0) + v
            for k, v in tenant_stats["language_distribution"].items():
                global_stats["language_distribution"][k] = global_stats["language_distribution"].get(k, 0) + v
            for k, v in tenant_stats["escalation_reason_distribution"].items():
                global_stats["escalation_reason_distribution"][k] = global_stats["escalation_reason_distribution"].get(k, 0) + v
                
            # Merge recent events
            global_stats["recent_events"].extend(tenant_stats["recent_events"])
            
        # Sort recent events by timestamp if available
        try:
            global_stats["recent_events"] = sorted(global_stats["recent_events"], key=_natural_sort_key)
        except Exception:
            pass
            
        global_stats["recent_events"] = global_stats["recent_events"][-100:]
        
        # Calculate running averages globally
        total = global_stats["total_queries"]
        if total > 0:
            global_stats["average_latency_ms"] = global_stats["_total_latency_ms"] / total
            global_stats["average_similarity_score"] = global_stats["_total_similarity_score"] / total
            global_stats["average_confidence_score"] = global_stats["_total_intent_confidence"] / total
            global_stats["escalation_rate"] = global_stats["escalation_count"] / total
            
        return {k: (dict(v) if isinstance(v, dict) else v) for k, v in global_stats.items() if not k.startswith("_")}
        
    else:
        tenant_stats = _get_tenant_stats(restaurant_id)
        return {k: (dict(v) if isinstance(v, dict) else v) for k, v in tenant_stats.items() if not k.startswith("_")}

def get_all_tenant_analytics() -> Dict[str, Dict[str, Any]]:
    """
    Returns a copy of the analytics for all active tenants,
    filtering out internal accumulator fields.
    """
    return {
        r_id: {k: (dict(v) if isinstance(v, dict) else v) 
               for k, v in tenant_stats.items() if not k.startswith("_")}
        for r_id, tenant_stats in _stats.items()
    }

def reset_session_analytics(restaurant_id: Optional[str] = None) -> None:
    """
    Resets all metrics and accumulators back to default for a specific restaurant or all.
    """
    if restaurant_id is None:
        _stats.clear()
    elif restaurant_id in _stats:
        _stats[restaurant_id] = _create_empty_stats()
