import re
from typing import Dict, Any, Optional

class EscalationEngine:
    """
    Escalation Rule Engine to determine if a customer query requires human
    intervention (PRD Module 7). Each rule can be toggled per restaurant via the
    `enabled_rules` map.
    """

    # Human assistance keyword search patterns
    HUMAN_ASSISTANCE_KEYWORDS = [
        r'\bmanager\b',
        r'\bhuman\b',
        r'\bsupport\s+agent\b',
        r'\brepresentative\b',
        r'\bcustomer\s+service\b',
        r'\bagent\b',
        r'\bstaff\b',
        r'\breal\s+person\b',
        r'\bspeak\s+to\s+someone\b',
        r'\btalk\s+to\s+someone\b'
    ]

    # Abuse / hostility patterns (PRD Module 7 "abuse detection"). Kept focused;
    # catches profanity and hostility directed at the service/agent.
    ABUSE_KEYWORDS = [
        r'\bf+u+c+k+\w*\b', r'\bf\*+ck\w*\b', r'\bs+h+i+t+\w*\b', r'\bsh\*+t\b',
        r'\basshole\b', r'\bbastard\b', r'\bidiot\b', r'\bstupid\b', r'\bmoron\b',
        r'\bshut\s+up\b', r'\buseless\b', r'\bpathetic\b', r'\bscrew\s+you\b',
        r'\bgo\s+to\s+hell\b', r'\bdamn\s+you\b', r'\bhate\s+you\b', r'\bcrap\b',
        r'\bbloody\s+\w+\b', r'\bnonsense\b',
    ]

    # Default: every rule enabled.
    _RULE_KEYS = ("refund", "complaint", "abuse", "human", "negative", "low_confidence")

    def _enabled(self, enabled_rules: Optional[Dict[str, bool]], key: str) -> bool:
        if not enabled_rules:
            return True
        return bool(enabled_rules.get(key, True))

    def _check_refund_inquiry(self, intent: str) -> Optional[Dict[str, Any]]:
        if intent == "Refund Inquiry":
            return {"escalate": True, "reason": "Refund Request"}
        return None

    def _check_complaint(self, intent: str) -> Optional[Dict[str, Any]]:
        if intent == "Complaint":
            return {"escalate": True, "reason": "Customer Complaint"}
        return None

    def _check_abuse(self, query: str) -> Optional[Dict[str, Any]]:
        """Detect abusive / hostile language directed at the service."""
        normalized = query.lower()
        for pattern in self.ABUSE_KEYWORDS:
            if re.search(pattern, normalized):
                return {"escalate": True, "reason": "Abusive Language"}
        return None

    def _check_human_assistance(self, query: str) -> Optional[Dict[str, Any]]:
        normalized_query = query.lower()
        for pattern in self.HUMAN_ASSISTANCE_KEYWORDS:
            if re.search(pattern, normalized_query):
                return {"escalate": True, "reason": "Human Assistance Requested"}
        return None

    def _check_negative_sentiment(self, sentiment: str) -> Optional[Dict[str, Any]]:
        if sentiment == "Negative":
            return {"escalate": True, "reason": "Negative Sentiment"}
        return None

    def _check_low_confidence(self, confidence: float, threshold: float = 0.60) -> Optional[Dict[str, Any]]:
        if confidence < threshold:
            return {"escalate": True, "reason": "Low Confidence"}
        return None

    def evaluate(self, intent: str, sentiment: str, confidence: float, query: str,
                 low_confidence_threshold: float = 0.60,
                 enabled_rules: Optional[Dict[str, bool]] = None) -> Dict[str, Any]:
        """
        Evaluate escalation rules in priority order (first match wins). Any rule
        can be disabled per restaurant via enabled_rules.
        """
        # Rule 1: Refund Inquiry
        if self._enabled(enabled_rules, "refund"):
            decision = self._check_refund_inquiry(intent)
            if decision:
                return decision

        # Rule 2: Complaint
        if self._enabled(enabled_rules, "complaint"):
            decision = self._check_complaint(intent)
            if decision:
                return decision

        # Rule 3: Abuse detection
        if self._enabled(enabled_rules, "abuse"):
            decision = self._check_abuse(query)
            if decision:
                return decision

        # Rule 4: Human Assistance Requested
        if self._enabled(enabled_rules, "human"):
            decision = self._check_human_assistance(query)
            if decision:
                return decision

        # Rule 5: Negative Sentiment
        if self._enabled(enabled_rules, "negative"):
            decision = self._check_negative_sentiment(sentiment)
            if decision:
                return decision

        # Rule 6: Low Confidence
        if self._enabled(enabled_rules, "low_confidence"):
            decision = self._check_low_confidence(confidence, low_confidence_threshold)
            if decision:
                return decision

        return {"escalate": False, "reason": "No Escalation Required"}
