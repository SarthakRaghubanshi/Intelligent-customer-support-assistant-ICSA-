import os
import sys
import datetime
import time
from dotenv import load_dotenv
import google.generativeai as genai

# A. Add the following imports
from backend.rag.retriever import retrieve_relevant_chunks
from backend.rag.prompt_builder import build_rag_prompt
from backend.classifiers.intent_classifier import classify_intent
from backend.analytics.event_logger import create_event
from backend.analytics.session_analytics import update_session_analytics

# B. Define a constant near the top of the file
restaurant_id = "Restaurant_A"

# Locate and load the .env file from the project root folder.
# This ensures it resolves correctly regardless of whether the app is run from root or frontend/
backend_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(backend_dir)
env_path = os.path.join(root_dir, ".env")

# Load variables into environment
load_dotenv(dotenv_path=env_path)

# Retrieve the API key
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# C. Modify ONLY def generate_response(user_message: str) -> str
def generate_response(user_message: str) -> str:
    """
    Sends a message to Google Gemini API grounded in the restaurant knowledge base,
    if similarity threshold check passes.
    
    Args:
        user_message (str): The chat prompt submitted by the user.
        
    Returns:
        str: The generated response from Gemini or a static fallback response.
        
    Raises:
        ValueError: If the user input is empty or the API key is missing.
        ConnectionError: If a network or connectivity issue occurs.
        RuntimeError: If the Gemini API returns an error or is unavailable.
    """
    # 1. Handle Empty Input
    if not user_message or not user_message.strip():
        raise ValueError("User message cannot be empty.")

    from backend.classifiers.sentiment_classifier import classify_sentiment

    # Start Timer for Latency Calculation
    start_time = time.perf_counter()

    # 1a. Run Intent Classification with Fault-Tolerant Fallback
    try:
        intent_result = classify_intent(user_message)
    except Exception:
        intent_result = {
            "intent": "Unknown",
            "confidence": 0.0,
            "layer": "Fallback"
        }

    # 1b. Run Sentiment Classification with Fault-Tolerant Fallback
    try:
        sentiment_result = classify_sentiment(user_message)
    except Exception:
        sentiment_result = {
            "sentiment": "Neutral",
            "confidence": 0.0,
            "layer": "Fallback"
        }

    # 1c. Run Language Detection with Fault-Tolerant Fallback
    from backend.classifiers.language_detector import detect_language
    try:
        language_result = detect_language(user_message)
    except Exception:
        language_result = {
            "language": "Unknown",
            "code": "unknown",
            "confidence": 0.0,
            "layer": "Fallback"
        }

    # 2. Handle Missing API Key
    if not GEMINI_API_KEY:
        raise ValueError(
            "GEMINI_API_KEY is missing. Please ensure you have created a '.env' file "
            "at the project root and added your key, for example:\n"
            "GEMINI_API_KEY=AIzaSy..."
        )

    # 3. Retrieve chunks using the RAG retriever (k=5)
    best_score = 1.0
    retrieved_sources = []
    try:
        relevant_chunks = retrieve_relevant_chunks(user_message, restaurant_id, k=5)
        if relevant_chunks:
            best_score = relevant_chunks[0]["score"]
            retrieved_sources = list(dict.fromkeys(
                chunk.get("source", "unknown") for chunk in relevant_chunks if chunk.get("source")
            ))
    except Exception as e:
        raise RuntimeError(f"Failed to retrieve context documents: {str(e)}")

    # 4. Read best similarity score & apply confidence threshold
    threshold = 0.75
    
    if relevant_chunks and best_score <= threshold:
        decision = "PASS_TO_GEMINI"
        response_source = "Gemini"
    else:
        decision = "FALLBACK"
        response_source = "System Fallback"

    # LOGGING REQUIREMENTS - Unified [PIPELINE_LOG]
    print(f"\n=================== [PIPELINE_LOG] ===================")
    print(f"Timestamp:             {datetime.datetime.now().isoformat()}")
    print(f"Query:                 {user_message}")
    print(f"Predicted Intent:      {intent_result['intent']}")
    print(f"Intent Confidence:     {intent_result['confidence']:.4f}")
    print(f"Intent Layer:          {intent_result['layer']}")
    print(f"Predicted Sentiment:   {sentiment_result['sentiment']}")
    print(f"Sentiment Confidence:  {sentiment_result['confidence']:.4f}")
    print(f"Sentiment Layer:       {sentiment_result['layer']}")
    print(f"Predicted Language:    {language_result['language']}")
    print(f"Language Code:         {language_result['code']}")
    print(f"Language Confidence:   {language_result['confidence']:.4f}")
    print(f"Language Layer:        {language_result['layer']}")
    print(f"RAG Used:              {decision == 'PASS_TO_GEMINI'}")
    print(f"Best Similarity Score: {best_score:.4f}")
    print(f"Threshold:             {threshold}")
    print(f"Decision:              {decision}")
    print(f"======================================================\n")

    # If best_score > 0.75, return fallback directly without calling Gemini
    if decision == "FALLBACK":
        response_text = "I could not find that information in the restaurant knowledge base."
    else:
        # 5. If best_score <= 0.75, build prompt and call Gemini
        metadata = {
            "intent": intent_result["intent"],
            "sentiment": sentiment_result["sentiment"],
            "language": language_result["language"],
            "language_code": language_result["code"]
        }
        grounded_prompt = build_rag_prompt(user_message, relevant_chunks, metadata=metadata)

        # Print the exact grounded prompt string before Gemini is called
        print(f"\n=================== [GROUNDED_PROMPT] ===================")
        print(grounded_prompt)
        print(f"==========================================================\n")

        # Configure Google Generative AI
        try:
            genai.configure(api_key=GEMINI_API_KEY)
        except Exception as e:
            raise RuntimeError(f"Failed to configure Gemini client: {str(e)}")

        # Generate Content via Gemini API
        try:
            # Using the standard lightweight and fast model: gemini-2.5-flash
            model = genai.GenerativeModel("gemini-2.5-flash")
            response = model.generate_content(grounded_prompt)
            
            # Verify the response object and its text field
            if response and response.text:
                response_text = response.text
            else:
                raise RuntimeError("Received an empty response from the Gemini API.")
                
        except Exception as e:
            error_msg = str(e).lower()
            
            # Categorize the API failure for user friendliness
            if "api_key_invalid" in error_msg or "key not valid" in error_msg:
                raise PermissionError(
                    "Invalid API Key. The GEMINI_API_KEY configured in your '.env' file "
                    "could not be authorized by Google."
                )
            elif "quota" in error_msg or "limit" in error_msg or "429" in error_msg:
                raise RuntimeError(
                    "Gemini API rate limit or quota exceeded. Please wait a moment and try again."
                )
            elif "conn" in error_msg or "dns" in error_msg or "socket" in error_msg or "unreachable" in error_msg:
                raise ConnectionError(
                    "Network Error: Unable to reach Google servers. Please check your internet connection."
                )
            else:
                raise RuntimeError(f"Gemini API Error: {str(e)}")

    # Calculate turn latency and generate event metadata (12 required fields)
    latency_ms = (time.perf_counter() - start_time) * 1000.0
    try:
        event = create_event({
            "timestamp": datetime.datetime.now().isoformat(),
            "restaurant_id": restaurant_id,
            "query": user_message,
            "intent": intent_result["intent"],
            "intent_confidence": intent_result["confidence"],
            "intent_layer": intent_result["layer"],
            "best_similarity_score": best_score,
            "rag_decision": decision,
            "retrieved_sources": retrieved_sources,
            "response_source": response_source,
            "response_length": len(response_text),
            "latency_ms": latency_ms
        })
    except Exception as e:
        print(f"Analytics event creation failed: {str(e)}", file=sys.stderr)
        event = None

    if event:
        try:
            update_session_analytics(event)
        except Exception as e:
            print(f"Session analytics update failed: {str(e)}", file=sys.stderr)

    return response_text
