import os
import sys

# Ensure project root is in path
current_file_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_file_dir)
if project_root not in sys.path:
    sys.path.append(project_root)

from backend.escalation.escalation_engine import EscalationEngine

def run_tests():
    print("=" * 80)
    print("RUNNING ESCALATION RULE ENGINE VERIFICATION TESTS")
    print("=" * 80)

    engine = EscalationEngine()
    passed_all = True

    # Test cases: (intent, sentiment, confidence, query, expected_escalate, expected_reason)
    test_cases = [
        # 1. Rule 1 (Refund Inquiry) Priority (triggers Refund Request)
        (
            "Refund Inquiry", 
            "Negative", 
            0.50, 
            "I want to speak to a manager, my order is wrong!", 
            True, 
            "Refund Request",
            "Rule 1: Refund Inquiry Priority"
        ),
        # 2. Rule 2 (Complaint) Priority (triggers Customer Complaint)
        (
            "Complaint", 
            "Negative", 
            0.50, 
            "Speak to a real person immediately", 
            True, 
            "Customer Complaint",
            "Rule 2: Complaint Priority"
        ),
        # 3. Rule 3 (Human Assistance) Priority (triggers Human Assistance Requested)
        (
            "Menu Inquiry", 
            "Negative", 
            0.50, 
            "Can I talk to someone please?", 
            True, 
            "Human Assistance Requested",
            "Rule 3: Human Assistance Priority"
        ),
        # 4. Rule 4 (Negative Sentiment) Priority (triggers Negative Sentiment)
        (
            "Menu Inquiry", 
            "Negative", 
            0.50, 
            "This pizza is awful.", 
            True, 
            "Negative Sentiment",
            "Rule 4: Negative Sentiment Priority"
        ),
        # 5. Rule 5 (Low Confidence) Priority (triggers Low Confidence)
        (
            "Menu Inquiry", 
            "Neutral", 
            0.50, 
            "What options do you have?", 
            True, 
            "Low Confidence",
            "Rule 5: Low Confidence Priority"
        ),
        # 6. Rule 3: Case-Insensitivity Check
        (
            "Menu Inquiry", 
            "Neutral", 
            0.90, 
            "I DEMAND TO TALK TO A REAL PERSON OR MANAGER", 
            True, 
            "Human Assistance Requested",
            "Rule 3: Case Insensitivity"
        ),
        # 7. No Escalation Triggered
        (
            "Menu Inquiry", 
            "Neutral", 
            0.90, 
            "How much is the margherita pizza?", 
            False, 
            "No Escalation Required",
            "Default: No Escalation"
        )
    ]

    for idx, (intent, sentiment, confidence, query, exp_esc, exp_reason, desc) in enumerate(test_cases, 1):
        print(f"[{idx}] Testing: {desc}")
        print(f"    Input  -> Intent: '{intent}', Sentiment: '{sentiment}', Confidence: {confidence}, Query: '{query}'")
        res = engine.evaluate(intent, sentiment, confidence, query)
        print(f"    Output -> Escalate: {res['escalate']}, Reason: '{res['reason']}'")
        
        match_esc = res['escalate'] == exp_esc
        match_reason = res['reason'] == exp_reason
        
        if match_esc and match_reason:
            print("    Status -> ✓ PASSED")
        else:
            print(f"    Status -> ✗ FAILED (Expected escalate={exp_esc}, reason='{exp_reason}')")
            passed_all = False
        print("-" * 80)

    print("=" * 80)
    if passed_all:
        print("✓ ALL ESCALATION RULE ENGINE VERIFICATION TESTS PASSED")
    else:
        print("✗ SOME ESCALATION RULE ENGINE VERIFICATION TESTS FAILED")
    print("=" * 80)
    
    if not passed_all:
        sys.exit(1)

if __name__ == "__main__":
    run_tests()
