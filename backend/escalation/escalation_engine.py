import re
from typing import Dict, Any, Optional

class EscalationEngine:
    """
    Escalation Rule Engine to determine if a customer query requires human intervention.
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

    def _check_refund_inquiry(self, intent: str) -> Optional[Dict[str, Any]]:
        """Rule 1: Refund Inquiry check."""
        if intent == "Refund Inquiry":
            return {"escalate": True, "reason": "Refund Request"}
        return None

    def _check_complaint(self, intent: str) -> Optional[Dict[str, Any]]:
        """Rule 2: Complaint check."""
        if intent == "Complaint":
            return {"escalate": True, "reason": "Customer Complaint"}
        return None

    def _check_human_assistance(self, query: str) -> Optional[Dict[str, Any]]:
        """Rule 3: Human Assistance check (case-insensitive keyword matching)."""
        normalized_query = query.lower()
        for pattern in self.HUMAN_ASSISTANCE_KEYWORDS:
            if re.search(pattern, normalized_query):
                return {"escalate": True, "reason": "Human Assistance Requested"}
        return None

    def _check_negative_sentiment(self, sentiment: str) -> Optional[Dict[str, Any]]:
        """Rule 4: Negative Sentiment check."""
        if sentiment == "Negative":
            return {"escalate": True, "reason": "Negative Sentiment"}
        return None

    def _check_low_confidence(self, confidence: float) -> Optional[Dict[str, Any]]:
        """Rule 5: Low Confidence check."""
        if confidence < 0.60:
            return {"escalate": True, "reason": "Low Confidence"}
        return None

    def evaluate(self, intent: str, sentiment: str, confidence: float, query: str) -> Dict[str, Any]:
        """
        Evaluates support conversation properties against predefined escalation rules in priority order.
        
        Args:
            intent (str): The predicted intent of the user message.
            sentiment (str): The predicted sentiment of the user message.
            confidence (float): The confidence score of the classification.
            query (str): The original user query.
            
        Returns:
            Dict[str, Any]: Dict containing escalation decision:
                            {
                                "escalate": bool,
                                "reason": str
                            }
        """
        # Rule 1: Refund Inquiry
        refund_decision = self._check_refund_inquiry(intent)
        if refund_decision:
            return refund_decision

        # Rule 2: Complaint
        complaint_decision = self._check_complaint(intent)
        if complaint_decision:
            return complaint_decision

        # Rule 3: Human Assistance Requested
        human_decision = self._check_human_assistance(query)
        if human_decision:
            return human_decision

        # Rule 4: Negative Sentiment
        sentiment_decision = self._check_negative_sentiment(sentiment)
        if sentiment_decision:
            return sentiment_decision

        # Rule 5: Low Confidence
        confidence_decision = self._check_low_confidence(confidence)
        if confidence_decision:
            return confidence_decision

        # Default case: No Escalation
        return {"escalate": False, "reason": "No Escalation Required"}
