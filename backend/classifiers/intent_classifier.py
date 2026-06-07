import os
import sys
import re
import json
from typing import Dict, Any, Optional
import google.generativeai as genai
from dotenv import load_dotenv

# Calibrated confidence mapping constant
INTENT_CONFIDENCE_MAP = {
    "General Greeting": 0.99,
    "Refund Inquiry": 0.95,
    "Order Tracking": 0.95,
    "Order Modification": 0.95,
    "Escalation Request": 0.95,
    "Menu Inquiry": 0.90,
    "Delivery Inquiry": 0.90,
    "Pickup Inquiry": 0.90,
    "Store Information": 0.90,
    "Complaint": 0.90
}

# Locate and load the .env file from the project root folder.
classifiers_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.dirname(classifiers_dir) if "classifiers" in classifiers_dir else classifiers_dir
root_dir = os.path.dirname(backend_dir)
env_path = os.path.join(root_dir, ".env")
load_dotenv(dotenv_path=env_path)

def classify_intent_rules(query: str) -> Optional[Dict[str, Any]]:
    """
    Evaluates basic keywords and regular expressions to determine
    the query's intent locally (Layer 1).
    """
    normalized = query.strip().lower()
    
    # 1. Order Modification (evaluated before Refund)
    if re.search(r'\bcancel\b.*\border\b', normalized) or \
       re.search(r'\bchange\b.*\border\b', normalized) or \
       re.search(r'\bmodify\b.*\border\b', normalized) or \
       re.search(r'\bedit\b.*\border\b', normalized) or \
       re.search(r'\bchange my order\b', normalized):
        intent = "Order Modification"
        return {"intent": intent, "confidence": INTENT_CONFIDENCE_MAP[intent], "layer": "Rule-Based"}

    # 2. Refund Inquiry
    if re.search(r'\brefund\b', normalized) or \
       re.search(r'\bmoney\s*back\b', normalized) or \
       re.search(r'\breimburse\b', normalized):
        intent = "Refund Inquiry"
        return {"intent": intent, "confidence": INTENT_CONFIDENCE_MAP[intent], "layer": "Rule-Based"}

    # 3. Order Tracking
    if re.search(r'\btrack\b', normalized) or \
       re.search(r'\bstatus\b', normalized) or \
       re.search(r'\bwhere\s*is\s*my\s*order\b', normalized):
        intent = "Order Tracking"
        return {"intent": intent, "confidence": INTENT_CONFIDENCE_MAP[intent], "layer": "Rule-Based"}

    # 4. Escalation Request
    if re.search(r'\bmanager\b', normalized) or \
       re.search(r'\bhuman\b', normalized) or \
       re.search(r'\bagent\b', normalized) or \
       re.search(r'\brepresentative\b', normalized) or \
       re.search(r'\bescalate\b', normalized):
        intent = "Escalation Request"
        return {"intent": intent, "confidence": INTENT_CONFIDENCE_MAP[intent], "layer": "Rule-Based"}

    # 5. Complaint
    if re.search(r'\bcold\b', normalized) or \
       re.search(r'\blate\b', normalized) or \
       re.search(r'\bwrong\b', normalized) or \
       re.search(r'\bburnt\b', normalized) or \
       re.search(r'\bhair\b', normalized) or \
       re.search(r'\bbad\b', normalized) or \
       re.search(r'\bhorrible\b', normalized) or \
       re.search(r'\bterrible\b', normalized) or \
       re.search(r'\bdisgusting\b', normalized) or \
       re.search(r'\bissue\b', normalized) or \
       re.search(r'\bproblem\b', normalized):
        intent = "Complaint"
        return {"intent": intent, "confidence": INTENT_CONFIDENCE_MAP[intent], "layer": "Rule-Based"}

    # 6. Menu Inquiry
    if re.search(r'\bmenu\b', normalized) or \
       re.search(r'\bpizza\b', normalized) or \
       re.search(r'\btopping\b', normalized) or \
       re.search(r'\bvegan\b', normalized) or \
       re.search(r'\bvegetarian\b', normalized) or \
       re.search(r'\bgluten\s*free\b', normalized) or \
       re.search(r'\bgluten-free\b', normalized) or \
       re.search(r'\bprice\b', normalized) or \
       re.search(r'\bcost\b', normalized) or \
       re.search(r'\bdish\b', normalized):
        intent = "Menu Inquiry"
        return {"intent": intent, "confidence": INTENT_CONFIDENCE_MAP[intent], "layer": "Rule-Based"}

    # 7. Delivery Inquiry
    if re.search(r'\bdelivery\b', normalized) or \
       re.search(r'\bdeliver\b', normalized):
        intent = "Delivery Inquiry"
        return {"intent": intent, "confidence": INTENT_CONFIDENCE_MAP[intent], "layer": "Rule-Based"}

    # 8. Pickup Inquiry
    if re.search(r'\bpickup\b', normalized) or \
       re.search(r'\bpick\s+up\b', normalized) or \
       re.search(r'\bcollect\b', normalized) or \
       re.search(r'\btakeaway\b', normalized):
        intent = "Pickup Inquiry"
        return {"intent": intent, "confidence": INTENT_CONFIDENCE_MAP[intent], "layer": "Rule-Based"}

    # 9. Store Information
    if re.search(r'\bhours\b', normalized) or \
       re.search(r'\bopen\b', normalized) or \
       re.search(r'\btimings\b', normalized) or \
       re.search(r'\baddress\b', normalized) or \
       re.search(r'\blocation\b', normalized) or \
       re.search(r'\bphone\b', normalized) or \
       re.search(r'\bcontact\b', normalized):
        intent = "Store Information"
        return {"intent": intent, "confidence": INTENT_CONFIDENCE_MAP[intent], "layer": "Rule-Based"}

    # 10. General Greeting
    if re.match(r'^(hello|hi|hey|good\s+morning|good\s+afternoon|good\s+evening|yo)(\s+.*)?$', normalized):
        words = normalized.split()
        if len(words) <= 3:
            intent = "General Greeting"
            return {"intent": intent, "confidence": INTENT_CONFIDENCE_MAP[intent], "layer": "Rule-Based"}

    return None

def classify_intent_gemini(query: str) -> Dict[str, Any]:
    """
    Sends the user message to Gemini API as fallback (Layer 2)
    to classify into one of the 11 intents in structured JSON.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return {"intent": "Out Of Scope", "confidence": 0.0, "layer": "Gemini-Based (Fallback - Missing Key)"}

    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-2.5-flash")

        system_instruction = (
            "You are a highly precise intent classification engine for a pizza restaurant support chatbot.\n"
            "Your task is to analyze the user's message and categorize it into exactly one of the following 11 intents:\n"
            "1. 'General Greeting': The user says hi, hello, how are you, greeting words.\n"
            "2. 'Menu Inquiry': The user asks about food, toppings, pizzas, ingredients, menu lists, vegan/gluten-free options, or prices.\n"
            "3. 'Delivery Inquiry': The user asks about delivery availability, zones, charges, times, or policies.\n"
            "4. 'Pickup Inquiry': The user asks about pick up options, timings, curbside, or coordinates.\n"
            "5. 'Refund Inquiry': The user asks about refunds, money back, or cancellation refunds.\n"
            "6. 'Store Information': The user asks about hours, timings, location, address, contact details.\n"
            "7. 'Complaint': The user complains about cold pizza, late delivery, wrong orders, bad food quality or service.\n"
            "8. 'Escalation Request': The user explicitly asks to speak to a manager, human agent, supervisor, or customer service representative.\n"
            "9. 'Order Tracking': The user asks where their order is, its tracking status, or tracking progress.\n"
            "10. 'Order Modification': The user wants to change, modify, cancel, edit, or update their existing order.\n"
            "11. 'Out Of Scope': The query is completely unrelated to the restaurant (e.g. general knowledge, science, math, other industries).\n\n"
            "CRITICAL BOUNDARY RULE:\n"
            "- 'Cancel my order' or requests to cancel must be categorized as 'Order Modification' (NOT 'Refund Inquiry').\n"
            "- 'I want a refund' or requests for money back must be categorized as 'Refund Inquiry'.\n\n"
            "You MUST return the output ONLY as a valid JSON object matching this schema:\n"
            "{\n"
            "  \"intent\": \"<intent_name>\",\n"
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
        intent = data.get("intent", "Out Of Scope")
        confidence = float(data.get("confidence", 0.0))
        return {"intent": intent, "confidence": confidence, "layer": "Gemini-Based"}
    except Exception as e:
        return {"intent": "Out Of Scope", "confidence": 0.0, "layer": f"Gemini-Based (Error: {str(e)})"}

def classify_intent(query: str) -> Dict[str, Any]:
    """
    Primary interface for hybrid intent classification.
    """
    if not query or not query.strip():
        return {"intent": "Out Of Scope", "confidence": 0.0, "layer": "Pre-processor"}

    # Run Layer 1: Rule-Based Classifier
    rule_result = classify_intent_rules(query)
    if rule_result is not None:
        return rule_result

    # Run Layer 2: Gemini-Based Fallback
    return classify_intent_gemini(query)

if __name__ == "__main__":
    test_queries = [
        "Hello",
        "Do you offer vegan pizza?",
        "What are your delivery charges?",
        "What are your pickup timings?",
        "Can I get a refund?",
        "My pizza arrived cold.",
        "Talk to a manager.",
        "Where is my order?",
        "Cancel my order.",
        "Who discovered gravity?"
    ]

    print("=" * 70)
    print("RUNNING INTENT CLASSIFIER VERIFICATION TEST SUITE")
    print("=" * 70)

    for idx, q in enumerate(test_queries, 1):
        result = classify_intent(q)
        print(f"[{idx}] Query: '{q}'")
        print(f"    Predicted Intent:     {result['intent']}")
        print(f"    Confidence:           {result['confidence']:.2f}")
        print(f"    Classification Layer: {result['layer']}")
        print("-" * 70)
