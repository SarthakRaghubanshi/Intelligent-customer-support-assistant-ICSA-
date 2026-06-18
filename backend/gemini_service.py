import os
import sys
from dotenv import load_dotenv
from typing import Dict, Any, Union
from backend.database.database import SessionLocal

# Locate and load the .env file from the project root folder.
# This ensures it resolves correctly regardless of whether the app is run from root or frontend/
backend_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(backend_dir)
env_path = os.path.join(root_dir, ".env")

# Load variables into environment
load_dotenv(dotenv_path=env_path)

# Retrieve the API key
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

from backend.classifiers.intent_classifier import classify_intent
from backend.classifiers.sentiment_classifier import classify_sentiment
from backend.classifiers.language_detector import detect_language
from backend.services.conversation_orchestrator import ConversationOrchestrator

def generate_response(user_message: str, restaurant_id: str = "Restaurant_A", return_dict: bool = False, db = None) -> Union[str, Dict[str, Any]]:
    """
    Sends a message to Google Gemini API grounded in the restaurant knowledge base,
    delegating the pipeline execution to ConversationOrchestrator.
    """
    if not user_message or not user_message.strip():
        raise ValueError("User message cannot be empty.")

    own_db = False
    if db is None:
        db = SessionLocal()
        own_db = True

    try:
        res_orch = ConversationOrchestrator.orchestrate(
            db=db,
            restaurant_id=restaurant_id,
            question=user_message,
            intent_classifier=classify_intent,
            sentiment_classifier=classify_sentiment,
            language_detector=detect_language
        )

        # Handle Gemini API failure/quota exceptions raised through the orchestrator/RAGService
        if res_orch.get("error") and res_orch.get("exception"):
            e = res_orch["exception"]
            error_msg = str(e).lower()
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

        if return_dict:
            return {
                "response": res_orch["answer"],
                "language": res_orch["language_info"],
                "intent": res_orch["intent"],
                "sentiment": res_orch["sentiment"],
                "confidence": res_orch["intent_info"].get("confidence", 0.0) if isinstance(res_orch.get("intent_info"), dict) else 0.0,
                "escalation": res_orch["escalation_result"]
            }
        else:
            return res_orch["answer"]
    finally:
        if own_db:
            db.close()
