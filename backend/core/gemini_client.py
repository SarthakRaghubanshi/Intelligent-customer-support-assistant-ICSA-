"""
Central Google Gemini configuration.

Single source of truth for the API key and model names so the LLM/embedding
settings live in one place instead of being re-read in every module. Import
`genai` (the configured client), `GEMINI_API_KEY`, `CHAT_MODEL`, or
`EMBED_MODEL` from here.
"""
import os
from dotenv import load_dotenv
import google.generativeai as genai

# Load .env from the project root regardless of the process launch directory.
_CORE_DIR = os.path.dirname(os.path.abspath(__file__))
_ROOT_DIR = os.path.dirname(os.path.dirname(_CORE_DIR))
load_dotenv(dotenv_path=os.path.join(_ROOT_DIR, ".env"))

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Model names (override via env if desired).
# gemini-2.5-flash is the default chat model — it is confirmed available on the
# free tier and produces grounded answers reliably. If your API key/plan offers
# a faster model, set GEMINI_CHAT_MODEL (e.g. "gemini-2.0-flash-lite" or
# "gemini-2.0-flash") for lower latency and higher throughput.
# Note: the Gemini FREE tier is rate-limited (a few requests/min and a capped
# daily total); the pipeline degrades gracefully to a fallback message on 429.
CHAT_MODEL = os.getenv("GEMINI_CHAT_MODEL", "gemini-2.5-flash")
EMBED_MODEL = os.getenv("GEMINI_EMBED_MODEL", "models/gemini-embedding-2")

# Configure the client once at import time if a key is present.
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)


def get_chat_model():
    """Return a configured GenerativeModel for chat/classification calls."""
    return genai.GenerativeModel(CHAT_MODEL)


def translate_text(text: str, target_language: str) -> str:
    """
    Translate a support message into target_language. Used so deterministic
    domain answers (order status, menu, recommendations) reply in the customer's
    language too — not just the RAG path. Returns the original text unchanged for
    English/Unknown, a missing key, or any API failure (graceful degradation).
    """
    if not text or not GEMINI_API_KEY:
        return text
    lang = (target_language or "").strip().lower()
    if lang in ("", "english", "unknown"):
        return text
    try:
        prompt = (
            f"Translate the following customer-support message into {target_language}. "
            "Keep order numbers, prices, currency symbols, and dish/item names exactly as-is. "
            "Return ONLY the translation, with no preamble or quotes.\n\n" + text
        )
        response = get_chat_model().generate_content(prompt)
        return response.text.strip() if response and response.text else text
    except Exception:
        return text
