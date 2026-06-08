import os
import sys
import unittest.mock as mock
import google.generativeai as genai

# Ensure project root is in path
current_file_dir = os.path.dirname(os.path.abspath(__file__))
if current_file_dir not in sys.path:
    sys.path.append(current_file_dir)
parent_dir = os.path.dirname(current_file_dir)
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

# Import files
from backend.gemini_service import generate_response
from backend.analytics.session_analytics import reset_session_analytics, get_session_analytics
from backend.analytics.event_logger import create_event

class MockResponse:
    def __init__(self, text):
        self.text = text

def mock_generate_content(*args, **kwargs):
    # Find prompt string in positional arguments
    prompt = ""
    for arg in args:
        if isinstance(arg, str):
            prompt = arg
            break
    if not prompt:
        # Check kwargs
        prompt = kwargs.get("contents", "")
        if not isinstance(prompt, str):
            prompt = str(prompt)
            
    prompt_lower = prompt.lower()
    
    # 1. Sentiment Classification Mock Responses
    if "sentiment" in prompt_lower:
        if "नमस्ते" in prompt_lower or "\\u0928\\u092e" in prompt_lower or "awful" in prompt_lower:
            return MockResponse('{"sentiment": "Negative", "confidence": 0.98}')
        else:
            return MockResponse('{"sentiment": "Neutral", "confidence": 0.95}')
            
    # 2. Intent Classification Mock Responses
    elif "intent" in prompt_lower or "categorize" in prompt_lower:
        if "नमस्ते" in prompt_lower or "\\u0928\\u092e" in prompt_lower:
            return MockResponse('{"intent": "Complaint", "confidence": 0.95}')
        elif "awful" in prompt_lower:
            return MockResponse('{"intent": "Complaint", "confidence": 0.98}')
        else:
            return MockResponse('{"intent": "Order Tracking", "confidence": 0.95}')
            
    # 3. Language Detection Mock Responses
    elif "language" in prompt_lower:
        if "नमस्ते" in prompt_lower:
            return MockResponse('{"language": "Hindi", "code": "hi", "confidence": 0.99}')
        else:
            return MockResponse('{"language": "English", "code": "en", "confidence": 0.95}')
            
    # 4. Response Generation Mock Responses
    else:
        return MockResponse("This is a mock response from Pizza Paradise support.")

def run_analytics_verification():
    print("=" * 80)
    print("RUNNING ANALYTICS EXPANSION VERIFICATION")
    print("=" * 80)
    
    # 1. Reset session statistics before execution
    reset_session_analytics()
    
    test_queries = [
        "Where is my order?",
        "नमस्ते, मेरा पिज्जा ठंडा आया।",
        "This is awful, my pizza is completely cold and ruined!"
    ]
    
    # Globally mock GenerativeModel.generate_content to prevent quota exhaustion
    with mock.patch("google.generativeai.generative_models.GenerativeModel.generate_content", side_effect=mock_generate_content):
        for idx, query in enumerate(test_queries, 1):
            print(f"\n[{idx}] Executing Query: '{query}'")
            print("-" * 50)
            
            try:
                response = generate_response(query)
                print(f"Response: {response}")
            except Exception as e:
                print(f"FAILED: {e}")
                
    # 2. Extract and assert session stats distributions
    stats = get_session_analytics()
    
    print("\n" + "=" * 80)
    print("AGGREGATED DISTRIBUTION VERIFICATION")
    print("=" * 80)
    print(f"Total Session Queries:        {stats.get('total_queries')}")
    print(f"Intent Distribution:          {stats.get('intent_distribution')}")
    print(f"Sentiment Distribution:       {stats.get('sentiment_distribution')}")
    print(f"Language Distribution:        {stats.get('language_distribution')}")
    print(f"Average Latency:              {stats.get('average_latency_ms')[-1] if isinstance(stats.get('average_latency_ms'), list) else stats.get('average_latency_ms'):.2f} ms")
    print(f"Average Similarity Score:     {stats.get('average_similarity_score'):.4f}")
    
    # Asserts
    assertions_passed = True
    errors = []
    
    # Check total count
    if stats.get("total_queries") != 3:
        assertions_passed = False
        errors.append(f"Expected 3 queries, got {stats.get('total_queries')}")
        
    # Check Intent distribution: 2 Complaint, 1 Order Tracking
    intents = stats.get("intent_distribution", {})
    if intents.get("Complaint") != 2 or intents.get("Order Tracking") != 1:
        assertions_passed = False
        errors.append(f"Incorrect intent distribution: {intents}")
        
    # Check Sentiment distribution: 2 Negative, 1 Neutral
    sentiments = stats.get("sentiment_distribution", {})
    if sentiments.get("Negative") != 2 or sentiments.get("Neutral") != 1:
        assertions_passed = False
        errors.append(f"Incorrect sentiment distribution: {sentiments}")
        
    # Check Language distribution: 2 English, 1 Hindi
    languages = stats.get("language_distribution", {})
    if languages.get("English") != 2 or languages.get("Hindi") != 1:
        assertions_passed = False
        errors.append(f"Incorrect language distribution: {languages}")
        
    if assertions_passed:
        print("✓ AGGREGATION ASSERTIONS PASSED\n")
    else:
        print(f"✗ AGGREGATION ASSERTIONS FAILED: {', '.join(errors)}\n")
        
    # 3. Test Backward Compatibility: Validate a legacy event with missing sentiment/language parameters
    print("=" * 80)
    print("BACKWARD COMPATIBILITY TEST WITH LEGACY EVENT")
    print("=" * 80)
    
    legacy_event = {
        "timestamp": "2026-01-01T00:00:00",
        "restaurant_id": "Restaurant_A",
        "query": "Legacy Test Query",
        "intent": "Order Tracking",
        "intent_confidence": 0.95,
        "intent_layer": "Rule-Based",
        "best_similarity_score": 0.50,
        "rag_decision": "PASS_TO_GEMINI",
        "retrieved_sources": [],
        "response_source": "Gemini",
        "response_length": 50,
        "latency_ms": 100
    }
    
    try:
        validated_event = create_event(legacy_event)
        
        # Verify default field insertion
        checks = {
            "sentiment": "Neutral",
            "sentiment_confidence": 0.0,
            "sentiment_layer": "Legacy",
            "language": "Unknown",
            "language_code": "unknown",
            "language_confidence": 0.0,
            "language_layer": "Legacy"
        }
        
        passed = True
        for field, expected in checks.items():
            actual = validated_event.get(field)
            if actual != expected:
                print(f"Mismatch: field '{field}' expected '{expected}', got '{actual}'")
                passed = False
                
        if passed:
            print("✓ BACKWARD COMPATIBILITY TEST PASSED")
            print("Validated Legacy Event schema complies and defaults are populated successfully via setdefault().")
        else:
            print("✗ BACKWARD COMPATIBILITY TEST FAILED: Default fields did not map correctly.")
            print(validated_event)
    except Exception as ex:
        print(f"✗ BACKWARD COMPATIBILITY TEST CRASHED: {ex}")
        
    print("=" * 80 + "\n")

if __name__ == "__main__":
    run_analytics_verification()
