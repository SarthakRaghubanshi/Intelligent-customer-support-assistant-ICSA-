import os
import sys
import re
import json
from typing import Dict, Any, Optional

# Ensure project root is in the Python path to load other modules
current_file_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.dirname(current_file_dir) if "classifiers" in current_file_dir else current_file_dir
root_dir = os.path.dirname(backend_dir)
if root_dir not in sys.path:
    sys.path.append(root_dir)
if backend_dir not in sys.path:
    sys.path.append(backend_dir)

# Consume the existing Gemini service state (genai client reference and pre-resolved API key)
# Removed top-level import to prevent circular dependencies.

SPANISH_KEYWORDS = {'hola', 'gracias', 'buenos', 'dias', 'como', 'estas', 'por', 'favor', 'buen', 'dia', 'adios'}
FRENCH_KEYWORDS = {'bonjour', 'merci', "s'il", 'vous', 'plait', 'comment', 'allez', 'ca', 'va', 'salut'}
GERMAN_KEYWORDS = {'hallo', 'danke', 'wie', 'geht', 'es', 'dir', 'guten', 'tag', 'bitte', 'tschüss'}
HINDI_KEYWORDS = {'नमस्ते', 'धन्यवाद', 'कैसे', 'हो', 'आप', 'हैं', 'शुक्रिया'}

ENGLISH_HINTS = {
    "hello",
    "hi",
    "how",
    "what",
    "where",
    "when",
    "why",
    "thank",
    "thanks",
    "please",
    "order",
    "pizza",
    "delivery",
    "menu",
    "status",
    "refund",
    "hours",
    "can",
    "could",
    "would",
    "my",
    "your"
}

def classify_language_rules(query: str) -> Optional[Dict[str, Any]]:
    """
    Evaluates rule-based logic to detect language locally (Layer 1).
    """
    normalized = query.strip().lower()

    # 1. Hindi Check: Devanagari range or explicit Hindi keywords
    has_devanagari = bool(re.search(r'[\u0900-\u097F]', query))
    has_hindi_keyword = any(kw in normalized for kw in HINDI_KEYWORDS)
    hindi_matches = has_devanagari or has_hindi_keyword

    # Extract Latin words
    latin_words = re.findall(r"\b[a-z']+\b", normalized)

    # 2. Spanish Check
    spanish_matches = any(w in SPANISH_KEYWORDS for w in latin_words)

    # 3. French Check
    french_matches = any(w in FRENCH_KEYWORDS for w in latin_words)

    # 4. German Check
    german_matches = any(w in GERMAN_KEYWORDS for w in latin_words)

    # 5. English Check
    # English should only be classified locally when:
    # - No Hindi, Spanish, French, or German patterns matched.
    # - Latin alphabet characters are present.
    # - At least one common English indicator (ENGLISH_HINTS) is present.
    # - If another language matches, we check if the non-keyword Latin words contain any English hints.
    english_matches = False
    if latin_words:
        other_kw = set()
        if spanish_matches:
            other_kw.update(SPANISH_KEYWORDS)
        if french_matches:
            other_kw.update(FRENCH_KEYWORDS)
        if german_matches:
            other_kw.update(GERMAN_KEYWORDS)
            
        non_other_words = [w for w in latin_words if w not in other_kw]
        
        if any(w in ENGLISH_HINTS for w in non_other_words):
            english_matches = True

    # Build the list of matching rules
    matches = []
    if hindi_matches:
        matches.append(("Hindi", "hi"))
    if spanish_matches:
        matches.append(("Spanish", "es"))
    if french_matches:
        matches.append(("French", "fr"))
    if german_matches:
        matches.append(("German", "de"))
    if english_matches:
        matches.append(("English", "en"))

    # Mixed-language handling: If more than one language rule matches, route to Gemini.
    if len(matches) > 1:
        # Determine dominant language (first non-English, or first matched language if all are English)
        non_english = [m for m in matches if m[0] != "English"]
        dom_lang, dom_code = non_english[0] if non_english else matches[0]
        return {
            "language": "Unknown",
            "code": "unknown",
            "confidence": 0.0,
            "layer": "Rule-Based Mixed",
            "fallback_language": dom_lang,
            "fallback_code": dom_code
        }

    if len(matches) == 1:
        lang, code = matches[0]
        return {
            "language": lang,
            "code": code,
            "confidence": 0.99 if lang != "English" else 0.90,
            "layer": "Rule-Based"
        }

    return None

def classify_language_gemini(query: str) -> Dict[str, Any]:
    """
    Sends the user message to Gemini API as fallback (Layer 2)
    to classify into English, Hindi, Spanish, French, German, or Unknown.
    """
    from backend.gemini_service import genai, GEMINI_API_KEY
    if not GEMINI_API_KEY:
        return {
            "language": "Unknown",
            "code": "unknown",
            "confidence": 0.0,
            "layer": "Fallback"
        }

    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel("gemini-2.5-flash")

        system_instruction = (
            "You are a highly precise language detection engine.\n"
            "Your task is to analyze the user's query and categorize it into exactly one of the following 5 languages or Unknown:\n"
            "1. 'English' (code: 'en')\n"
            "2. 'Hindi' (code: 'hi')\n"
            "3. 'Spanish' (code: 'es')\n"
            "4. 'French' (code: 'fr')\n"
            "5. 'German' (code: 'de')\n"
            "6. 'Unknown' (code: 'unknown')\n\n"
            "You MUST return the output ONLY as a valid JSON object matching this schema:\n"
            "{\n"
            "  \"language\": \"<English|Hindi|Spanish|French|German|Unknown>\",\n"
            "  \"code\": \"<en|hi|es|fr|de|unknown>\",\n"
            "  \"confidence\": <float between 0.0 and 1.0>\n"
            "}\n"
            "Do not include any formatting, codeblocks, backticks, or other text outside the JSON object."
        )

        prompt = f"System Instructions:\n{system_instruction}\n\nUser Message: {query}\n\nJSON Output:"
        response = model.generate_content(prompt)
        
        resp_text = response.text.strip()
        if resp_text.startswith("```json"):
            resp_text = resp_text[7:]
        if resp_text.endswith("```"):
            resp_text = resp_text[:-3]
        resp_text = resp_text.strip()

        data = json.loads(resp_text)
        language = data.get("language", "Unknown")
        code = data.get("code", "unknown")
        confidence = float(data.get("confidence", 0.0))
        return {
            "language": language,
            "code": code,
            "confidence": confidence,
            "layer": "Gemini-Based"
        }
    except Exception:
        return {
            "language": "Unknown",
            "code": "unknown",
            "confidence": 0.0,
            "layer": "Fallback"
        }

def detect_language(query: str) -> Dict[str, Any]:
    """
    Primary interface for hybrid language detection with improved mixed-language fault isolation.
    """
    if not query or not query.strip():
        return {
            "language": "Unknown",
            "code": "unknown",
            "confidence": 0.0,
            "layer": "Pre-processor"
        }

    # Run Layer 1: Rule-Based Detection
    rule_result = classify_language_rules(query)
    if rule_result is not None:
        # If it matched mixed-languages, rule_result has code 'unknown' and layer 'Rule-Based Mixed'.
        if rule_result["layer"] == "Rule-Based Mixed":
            gemini_res = classify_language_gemini(query)
            if gemini_res["confidence"] > 0.0 and gemini_res["language"] != "Unknown":
                gemini_res["layer"] = f"Gemini-Based (Fallback from {rule_result['layer']})"
                return gemini_res
            else:
                # Gemini failed or rate-limited: Return dominant rule-based language
                return {
                    "language": rule_result["fallback_language"],
                    "code": rule_result["fallback_code"],
                    "confidence": 0.60,
                    "layer": "Rule-Based Mixed Fallback"
                }
        return rule_result

    # Run Layer 2: Gemini-Based Fallback
    return classify_language_gemini(query)

if __name__ == "__main__":
    verification_cases = [
        {"query": "Hello, how are you?", "expected": "English"},
        {"query": "नमस्ते, आप कैसे हैं?", "expected": "Hindi"},
        {"query": "Hola, ¿cómo estás?", "expected": "Spanish"},
        {"query": "Bonjour, comment allez-vous?", "expected": "French"},
        {"query": "Hallo, wie geht es dir?", "expected": "German"},
        {"query": "Hola, my order is late", "expected": "Mixed (Spanish/English) -> Gemini Fallback / Spanish Fallback"},
        {"query": "नमस्ते, where is my pizza?", "expected": "Mixed (Hindi/English) -> Gemini Fallback / Hindi Fallback"},
        {"query": "asdfghjkl", "expected": "Unknown / Gemini Fallback"},
        {"query": "asdf qwer zxcv", "expected": "Unknown / Gemini Fallback"},
        {"query": "abc def ghi", "expected": "Unknown / Gemini Fallback"},
        {"query": "Where is my order?", "expected": "English"},
        {"query": "Thank you for the delivery", "expected": "English"}
    ]

    print("=" * 80)
    print("RUNNING LANGUAGE DETECTOR VERIFICATION")
    print("=" * 80)

    routing_report = []

    for idx, case in enumerate(verification_cases, 1):
        q = case["query"]
        expected = case["expected"]
        
        result = detect_language(q)
        
        # Determine routing logic for presentation
        rule_res = classify_language_rules(q)
        if rule_res is not None:
            if rule_res["layer"] == "Rule-Based Mixed":
                if "Fallback" in result["layer"]:
                    routing = "Rule-Based Mixed -> Gemini Failed"
                    api_status = "Failed (Rate Limit/Exception)"
                else:
                    routing = "Rule-Based Mixed -> Gemini Success"
                    api_status = "Succeeded"
            else:
                routing = "Rule-Based Layer"
                api_status = "Skipped (Handled Locally)"
        else:
            routing = "Attempted Gemini Fallback"
            if result["layer"] == "Fallback":
                api_status = "Failed (Rate Limit/Exception)"
            else:
                api_status = "Succeeded"
                
        routing_report.append({
            "idx": idx,
            "query": q,
            "routing": routing,
            "api_status": api_status,
            "predicted": result["language"],
            "code": result["code"],
            "expected": expected,
            "layer": result["layer"],
            "confidence": result["confidence"]
        })

        print(f"[{idx}] Query: '{q}'")
        print(f"    Expected:             {expected}")
        print(f"    Predicted Language:   {result['language']} (code: {result['code']})")
        print(f"    Confidence:           {result['confidence']:.2f}")
        print(f"    Layer:                {result['layer']}")
        print(f"    Routing:              {routing}")
        print(f"    API Call Status:      {api_status}")
        print("-" * 80)

    print("\n" + "=" * 80)
    print("LANGUAGE DETECTION ROUTING REPORT")
    print("=" * 80)
    print(f"{'Idx':<4} | {'Query':<30} | {'Routing Logic':<35} | {'Predicted (Code)':<20} | {'API Status':<15}")
    print("-" * 115)
    for r in routing_report:
        pred_str = f"{r['predicted']} ({r['code']})"
        print(f"{r['idx']:<4} | {r['query']:<30} | {r['routing']:<35} | {pred_str:<20} | {r['api_status']:<15}")
    print("=" * 80 + "\n")
