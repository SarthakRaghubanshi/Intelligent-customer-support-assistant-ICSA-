import uuid
import datetime
from typing import Dict, Any

def create_event(event_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Creates and validates an AnalyticsEvent dictionary.
    Generates a unique turn UUID (event_id) internally.
    Prints the completed 13-field event to stdout under the [EVENT_LOG] prefix.
    
    Args:
        event_data (Dict[str, Any]): Dictionary containing 12 required fields
                                      (excluding event_id).
                                      
    Returns:
        Dict[str, Any]: The fully validated 13-field event object.
    """
    # 1. Generate unique event_id internally
    event_data["event_id"] = str(uuid.uuid4())

    # Safe defaults for backward compatibility
    event_data.setdefault("sentiment", "Neutral")
    event_data.setdefault("sentiment_confidence", 0.0)
    event_data.setdefault("sentiment_layer", "Legacy")
    event_data.setdefault("language", "Unknown")
    event_data.setdefault("language_code", "unknown")
    event_data.setdefault("language_confidence", 0.0)
    event_data.setdefault("language_layer", "Legacy")

    # 2. Schema field validations for the 20 resulting fields
    required_fields = {
        "event_id": str,
        "timestamp": str,
        "restaurant_id": str,
        "query": str,
        "intent": str,
        "intent_confidence": float,
        "intent_layer": str,
        "sentiment": str,
        "sentiment_confidence": float,
        "sentiment_layer": str,
        "language": str,
        "language_code": str,
        "language_confidence": float,
        "language_layer": str,
        "best_similarity_score": float,
        "rag_decision": str,
        "retrieved_sources": list,
        "response_source": str,
        "response_length": int,
        "latency_ms": float
    }

    # Verify presence and type schema
    for field, field_type in required_fields.items():
        if field not in event_data:
            raise KeyError(f"Missing required analytics field: '{field}'")
        
        val = event_data[field]
        # Calibrate types: convert int to float for scores/latencies if needed
        if field_type == float and isinstance(val, int):
            event_data[field] = float(val)
            val = float(val)
            
        if not isinstance(val, field_type):
            raise TypeError(
                f"Incorrect type for field '{field}'. Expected {field_type.__name__}, got {type(val).__name__}"
            )

    # 3. Print completed event log with prefix [EVENT_LOG]
    print(f"\n=================== [EVENT_LOG] ===================")
    print(f"Event ID:              {event_data['event_id']}")
    print(f"Timestamp:             {event_data['timestamp']}")
    print(f"Restaurant ID:         {event_data['restaurant_id']}")
    print(f"Query:                 {event_data['query']}")
    print(f"Predicted Intent:      {event_data['intent']}")
    print(f"Confidence Score:      {event_data['intent_confidence']:.4f}")
    print(f"Classification Layer:  {event_data['intent_layer']}")
    print(f"Predicted Sentiment:   {event_data['sentiment']}")
    print(f"Sentiment Confidence:  {event_data['sentiment_confidence']:.4f}")
    print(f"Sentiment Layer:       {event_data['sentiment_layer']}")
    print(f"Predicted Language:    {event_data['language']}")
    print(f"Language Code:         {event_data['language_code']}")
    print(f"Language Confidence:   {event_data['language_confidence']:.4f}")
    print(f"Language Layer:        {event_data['language_layer']}")
    print(f"Best Similarity Score: {event_data['best_similarity_score']:.4f}")
    print(f"RAG Decision:          {event_data['rag_decision']}")
    print(f"Retrieved Sources:     {event_data['retrieved_sources']}")
    print(f"Response Source:       {event_data['response_source']}")
    print(f"Response Length:       {event_data['response_length']} chars")
    print(f"Latency MS:            {event_data['latency_ms']:.2f} ms")
    print(f"=====================================================\n")

    return event_data
