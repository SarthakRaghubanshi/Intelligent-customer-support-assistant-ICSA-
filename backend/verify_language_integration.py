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

# Setup isolated test database path
test_db_path = os.path.join(parent_dir, "data", "test_language_integration.db")
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

# Import the service function
from backend.gemini_service import generate_response

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
    if "intent" in prompt_lower or "categorize" in prompt_lower:
        # Intent classification prompt mock response
        return MockResponse('{"intent": "Out Of Scope", "confidence": 0.95}')
    elif "sentiment" in prompt_lower:
        # Sentiment classification prompt mock response
        return MockResponse('{"sentiment": "Neutral", "confidence": 0.90}')
    elif "language" in prompt_lower:
        # Language classification prompt mock response
        return MockResponse('{"language": "Spanish", "code": "es", "confidence": 0.90}')
    else:
        # Response generation prompt mock response
        return MockResponse("This is a mock response from Pizza Paradise support.")

def run_test_case(query: str, simulate_gemini_failure: bool = False):
    print("=" * 80)
    print(f"QUERY: {query}")
    if simulate_gemini_failure:
        print("(Simulating Gemini Fallback Failure/Quota Exhaustion)")
    print("=" * 80)
    
    # Capture standard output to verify logs and prompt contents
    import io
    stdout_capture = io.StringIO()
    original_stdout = sys.stdout
    sys.stdout = stdout_capture
    
    try:
        # Globally mock generate_content to avoid API quota errors
        with mock.patch("google.generativeai.generative_models.GenerativeModel.generate_content", side_effect=mock_generate_content):
            if simulate_gemini_failure:
                # Mock classify_language_gemini to simulate Gemini API failure/quota exhaustion
                dummy_fallback = {
                    "language": "Unknown",
                    "code": "unknown",
                    "confidence": 0.0,
                    "layer": "Fallback"
                }
                with mock.patch("backend.classifiers.language_detector.classify_language_gemini", return_value=dummy_fallback):
                    response = generate_response(query)
            else:
                response = generate_response(query)
    except Exception as e:
        sys.stdout = original_stdout
        print(f"ERROR: generate_response failed with: {e}")
        return
        
    sys.stdout = original_stdout
    captured_logs = stdout_capture.getvalue()
    
    # Print the captured logs
    print(captured_logs)
    print(f"RESPONSE:\n{response}\n")
    
    # Perform assertions/checks to output validation summary
    validation_passed = True
    reasons = []
    
    # 1. Pipeline Log check
    if "[PIPELINE_LOG]" not in captured_logs:
        validation_passed = False
        reasons.append("Missing [PIPELINE_LOG] in logs.")
    
    # 2. Grounded Prompt check (only if RAG used)
    rag_used = "RAG Used:              True" in captured_logs
    if rag_used:
        if "[GROUNDED_PROMPT]" not in captured_logs:
            validation_passed = False
            reasons.append("Missing [GROUNDED_PROMPT] in logs.")
        else:
            # Metadata ordering check: Detected Intent, Detected Sentiment, Detected Language before User Query
            prompt_part = captured_logs.split("[GROUNDED_PROMPT]")[1].split("==========================================================")[0]
            
            idx_intent = prompt_part.find("Detected Intent:")
            idx_sentiment = prompt_part.find("Detected Sentiment:")
            idx_language = prompt_part.find("Detected Language:")
            idx_user_query = prompt_part.find("User Query:")
            
            if idx_intent == -1 or idx_sentiment == -1 or idx_language == -1 or idx_user_query == -1:
                validation_passed = False
                reasons.append("One or more expected metadata header fields are missing in grounded prompt.")
            elif not (idx_intent < idx_sentiment < idx_language < idx_user_query):
                validation_passed = False
                reasons.append("Metadata fields are not ordered correctly in grounded prompt header.")
    
    # 3. Query specific checks
    if query == "Where is my order?":
        if "Predicted Language:    English" not in captured_logs or "Language Layer:        Rule-Based" not in captured_logs:
            validation_passed = False
            reasons.append("English was not classified locally under Rule-Based layer.")
            
    elif query == "Bonjour, comment allez-vous?":
        if "Predicted Language:    French" not in captured_logs or "Language Layer:        Rule-Based" not in captured_logs:
            validation_passed = False
            reasons.append("French was not classified locally under Rule-Based layer.")
        # Check that English is NOT detected
        if "Predicted Language:    English" in captured_logs:
            validation_passed = False
            reasons.append("English was falsely detected for French query.")
            
    elif query == "Hola, my order is late" and simulate_gemini_failure:
        if "Predicted Language:    Spanish" not in captured_logs or "Language Layer:        Rule-Based Mixed Fallback" not in captured_logs:
            validation_passed = False
            reasons.append("Spanish dominant mixed fallback failed under simulated Gemini failure.")
            
    if validation_passed:
        print("✓ VALIDATION STATUS: PASSED\n")
    else:
        print(f"✗ VALIDATION STATUS: FAILED (Reasons: {', '.join(reasons)})\n")

if __name__ == "__main__":
    test_queries = [
        ("Where is my order?", False),
        ("नमस्ते, मेरा पिज्जा ठंडा आया।", False),
        ("Bonjour, comment allez-vous?", False),
        ("Hola, my order is late", True) # Verify simulated Gemini failure case
    ]
    
    print("=" * 80)
    print("RUNNING LANGUAGE INTEGRATION VERIFICATION SUITE")
    print("=" * 80)
    
    try:
        for q, fail_mock in test_queries:
            run_test_case(q, fail_mock)
    finally:
        # Clean up database files and folder
        if os.path.exists(test_db_path):
            try:
                os.remove(test_db_path)
            except Exception:
                pass
        
    print("=" * 80)
    print("VERIFICATION SUITE COMPLETED")
    print("=" * 80)
