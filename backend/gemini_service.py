import os
import sys
import datetime
from dotenv import load_dotenv
import google.generativeai as genai

# A. Add the following imports
from backend.rag.retriever import retrieve_relevant_chunks
from backend.rag.prompt_builder import build_rag_prompt
from backend.classifiers.intent_classifier import classify_intent

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

    # 1a. Run Intent Classification with Fault-Tolerant Fallback
    try:
        intent_result = classify_intent(user_message)
    except Exception:
        intent_result = {
            "intent": "Unknown",
            "confidence": 0.0,
            "layer": "Fallback"
        }

    # Compile intent metadata
    intent_metadata = {
        "timestamp": datetime.datetime.now().isoformat(),
        "query": user_message,
        "intent": intent_result["intent"],
        "confidence": intent_result["confidence"],
        "layer": intent_result["layer"]
    }

    # Log intent metadata to console
    print(f"\n=================== [INTENT_LOG] ===================")
    print(f"Timestamp:             {intent_metadata['timestamp']}")
    print(f"Query:                 {intent_metadata['query']}")
    print(f"Predicted Intent:      {intent_metadata['intent']}")
    print(f"Confidence Score:      {intent_metadata['confidence']:.4f}")
    print(f"Classification Layer:  {intent_metadata['layer']}")
    print(f"=====================================================\n")

    # 2. Handle Missing API Key
    if not GEMINI_API_KEY:
        raise ValueError(
            "GEMINI_API_KEY is missing. Please ensure you have created a '.env' file "
            "at the project root and added your key, for example:\n"
            "GEMINI_API_KEY=AIzaSy..."
        )

    # 3. Retrieve chunks using the RAG retriever (k=5)
    try:
        relevant_chunks = retrieve_relevant_chunks(user_message, restaurant_id, k=5)
    except Exception as e:
        raise RuntimeError(f"Failed to retrieve context documents: {str(e)}")

    # 4. Read best similarity score & apply confidence threshold
    threshold = 0.75
    
    if not relevant_chunks:
        # Fallback if no chunks found at all
        best_score = 1.0
        decision = "FALLBACK"
    else:
        best_score = relevant_chunks[0]["score"]
        if best_score > threshold:
            decision = "FALLBACK"
        else:
            decision = "PASS_TO_GEMINI"

    # LOGGING REQUIREMENTS
    print(f"\n=================== RAG DECISION LOG ===================")
    print(f"User Query: {user_message}")
    print(f"Best Similarity Score: {best_score:.4f}")
    print(f"Threshold: {threshold}")
    print(f"Decision: {decision}")
    print(f"========================================================\n")

    # If best_score > 0.75, return fallback directly without calling Gemini
    if decision == "FALLBACK":
        return "I could not find that information in the restaurant knowledge base."

    # 5. If best_score <= 0.75, build prompt and call Gemini
    grounded_prompt = build_rag_prompt(user_message, relevant_chunks)

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
            return response.text
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
