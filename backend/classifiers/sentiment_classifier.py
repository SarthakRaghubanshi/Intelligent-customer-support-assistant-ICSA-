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

# Rule-layer confidence is derived from how strongly the text matches (number of
# sentiment cues), NOT a flat constant — a single weak cue scores lower than
# several strong ones, so the value actually reflects the input signal.
def _signal_confidence(match_count: int, base: float, step: float, cap: float) -> float:
    return round(min(cap, base + step * match_count), 2)


def classify_sentiment_rules(query: str) -> Optional[Dict[str, Any]]:
    """
    Evaluates basic keywords and regular expressions to determine
    the query's sentiment locally (Layer 1). Confidence scales with the number
    of matched cues (signal strength).
    """
    normalized = query.strip().lower()

    # Define keyword regex patterns
    pos_pattern = r'\b(excellent|amazing|great|awesome|love[ds]?|fantastic|wonderful|good|perfect|delicious|happy|thank)\b'
    neg_pattern = (
        r'\b(bad|terrible|worst|cold\s+food|late\s+delivery|burnt\s+food|cold|burnt|late|awful|horrible|poor|disappointed|angry|unacceptable|refund|disgusting|ruined)\b|'
        r'\bslow\s+delivery\b|'
        r'\bdelivery\s+(was|is)\s+slow\b|'
        r'\bservice\s+(was|is)\s+slow\b|'
        r'\border\s+(was|is)\s+slow\b'
    )
    neutral_pattern = (
        r'\b(opening\s+hours|location|menu|delivery\s+area|pricing|contact\s+information|contact\s+info|'
        r'price|cost|address|phone\s+number|store\s+hours|delivery\s+time|pickup\s+information)\b'
    )

    pos_count = len(re.findall(pos_pattern, normalized))
    neg_count = len(re.findall(neg_pattern, normalized))
    neutral_count = len(re.findall(neutral_pattern, normalized))

    # 1. Mixed Sentiment Check: If both positive and negative signals are found, route to Gemini.
    if pos_count and neg_count:
        return None

    # 2. Obvious Positive Check — confidence grows with the number of positive cues.
    if pos_count:
        return {
            "sentiment": "Positive",
            "confidence": _signal_confidence(pos_count, base=0.62, step=0.12, cap=0.96),
            "layer": "Rule-Based",
        }

    # 3. Obvious Negative Check
    if neg_count:
        return {
            "sentiment": "Negative",
            "confidence": _signal_confidence(neg_count, base=0.64, step=0.12, cap=0.97),
            "layer": "Rule-Based",
        }

    # 4. Obvious Neutral Check — inherently a weaker signal, so lower confidence.
    if neutral_count:
        return {
            "sentiment": "Neutral",
            "confidence": _signal_confidence(neutral_count, base=0.55, step=0.08, cap=0.85),
            "layer": "Rule-Based",
        }

    return None

def classify_sentiment_gemini(query: str) -> Dict[str, Any]:
    """
    Sends the user message to Gemini API as fallback (Layer 2)
    to classify into Positive, Neutral, or Negative in structured JSON.
    """
    from backend.core.gemini_client import genai, GEMINI_API_KEY, CHAT_MODEL
    if not GEMINI_API_KEY:
        return {"sentiment": "Neutral", "confidence": 0.0, "layer": "Gemini-Based (Fallback - Missing Key)"}

    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel(CHAT_MODEL)

        system_instruction = (
            "You are a highly precise sentiment classification engine for a pizza restaurant support chatbot.\n"
            "Your task is to analyze the user's message and categorize it into exactly one of the following 3 sentiments:\n"
            "1. 'Positive': The user expresses satisfaction, happiness, praise, or gratitude.\n"
            "2. 'Negative': The user expresses dissatisfaction, complaints, anger, frustration, or disappointment.\n"
            "3. 'Neutral': The user asks standard informational questions, store hours, menus, without emotional bias.\n\n"
            "You MUST return the output ONLY as a valid JSON object matching this schema:\n"
            "{\n"
            "  \"sentiment\": \"<Positive|Neutral|Negative>\",\n"
            "  \"confidence\": <float between 0.0 and 1.0>\n"
            "}\n"
            "Do not include any formatting, codeblocks, backticks, or other text outside the JSON object."
        )

        prompt = f"System Instructions:\n{system_instruction}\n\nUser Message: {query}\n\nJSON Output:"
        response = model.generate_content(prompt)
        
        resp_text = response.text.strip()
        # Strip markdown syntax if returned
        if resp_text.startswith("```json"):
            resp_text = resp_text[7:]
        if resp_text.endswith("```"):
            resp_text = resp_text[:-3]
        resp_text = resp_text.strip()

        data = json.loads(resp_text)
        sentiment = data.get("sentiment", "Neutral")
        confidence = float(data.get("confidence", 0.0))
        return {"sentiment": sentiment, "confidence": confidence, "layer": "Gemini-Based"}
    except Exception as e:
        return {"sentiment": "Neutral", "confidence": 0.0, "layer": f"Gemini-Based (Error: {str(e)})"}

def classify_sentiment(query: str) -> Dict[str, Any]:
    """
    Primary interface for hybrid sentiment classification.
    """
    if not query or not query.strip():
        return {"sentiment": "Neutral", "confidence": 0.0, "layer": "Pre-processor"}

    # Run Layer 1: Rule-Based Classifier
    rule_result = classify_sentiment_rules(query)
    if rule_result is not None:
        return rule_result

    # Run Layer 2: Gemini-Based Fallback
    return classify_sentiment_gemini(query)

if __name__ == "__main__":
    verification_cases = [
        {"query": "Excellent pizza, loved it.", "expected": "Positive"},
        {"query": "My food arrived cold.", "expected": "Negative"},
        {"query": "What are your opening hours?", "expected": "Neutral"},
        {"query": "The pizza was good but delivery was slow.", "expected": "Mixed (Gemini-Based)"},
        {"query": "The experience was okay.", "expected": "Mixed/Ambiguous (Gemini-Based)"}
    ]

    print("=" * 80)
    print("RUNNING SENTIMENT CLASSIFIER VERIFICATION")
    print("=" * 80)

    routing_report = []

    for idx, case in enumerate(verification_cases, 1):
        q = case["query"]
        expected = case["expected"]
        
        # Determine routing behavior prior to executing full classify_sentiment
        rule_res = classify_sentiment_rules(q)
        if rule_res is not None:
            routing = "Rule-Based Layer"
            api_status = "Skipped (Handled Locally)"
            result = rule_res
        else:
            routing = "Attempted Gemini Fallback"
            result = classify_sentiment_gemini(q)
            if "Error" in result["layer"] or result["confidence"] == 0.0:
                api_status = "Failed (Rate Limit/Exception)"
            else:
                api_status = "Succeeded"
                
        routing_report.append({
            "idx": idx,
            "query": q,
            "routing": routing,
            "api_status": api_status,
            "predicted": result["sentiment"],
            "expected": expected,
            "layer": result["layer"],
            "confidence": result["confidence"]
        })

        print(f"[{idx}] Query: '{q}'")
        print(f"    Expected Sentiment:   {expected}")
        print(f"    Predicted Sentiment:  {result['sentiment']}")
        print(f"    Confidence:           {result['confidence']:.2f}")
        print(f"    Classification Layer: {result['layer']}")
        print(f"    Routing Resolution:   {routing}")
        print(f"    API Call Status:      {api_status}")
        print("-" * 80)

    print("\n" + "=" * 80)
    print("ROUTING & VERIFICATION SUMMARY REPORT")
    print("=" * 80)
    print(f"{'Idx':<4} | {'Query':<42} | {'Routing Logic':<25} | {'API Fallback Status':<30}")
    print("-" * 110)
    for r in routing_report:
        print(f"{r['idx']:<4} | {r['query']:<42} | {r['routing']:<25} | {r['api_status']:<30}")
    print("=" * 80 + "\n")
