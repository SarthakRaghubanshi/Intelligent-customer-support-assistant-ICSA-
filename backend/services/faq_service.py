"""
Smart FAQ Engine (PRD Module 5).

A dedicated FAQ layer that is distinct from the generic RAG pipeline: it parses a
restaurant's curated FAQ document (the ingested `faq` knowledge doc, formatted as
"Q1: ... A1: ...") into question/answer pairs and returns the EXACT stored answer
when the customer's question matches a curated question with enough keyword
overlap. The answer is returned verbatim and deterministically — no LLM, so
common questions (delivery charges, pickup, refund policy, payment, hours) are
answered instantly and can never be hallucinated.

If no curated FAQ matches confidently, `answer()` returns None and the caller
falls back to the RAG knowledge pipeline.
"""
import re
from typing import Optional, Dict, Any, List, Tuple, Set
from sqlalchemy.orm import Session

from backend.repositories.knowledge_repository import KnowledgeRepository

# Parse "Q1: <question>  A1: <answer>" blocks (answers may span multiple lines).
_QA_RE = re.compile(r'Q\d+\s*[:.\-]\s*(.+?)\s*A\d+\s*[:.\-]\s*(.+?)(?=\s*Q\d+\s*[:.\-]|\Z)', re.DOTALL | re.IGNORECASE)

_STOPWORDS: Set[str] = {
    "the", "and", "for", "are", "you", "your", "our", "can", "could", "would",
    "what", "how", "does", "did", "with", "from", "any", "some", "have", "has",
    "will", "this", "that", "there", "here", "get", "got", "was", "were", "been",
    "about", "into", "when", "where", "which", "whom", "who", "why", "not", "but",
    "please", "tell", "know", "want", "need", "give", "make", "take", "use",
}

_MIN_SCORE = 0.30       # Jaccard threshold on significant tokens
_MIN_SHARED = 2         # require at least this many shared keywords


def _tokens(text: str) -> Set[str]:
    return {w for w in re.findall(r"[a-z]+", (text or "").lower()) if len(w) > 2 and w not in _STOPWORDS}


def _parse_faqs(db: Session, restaurant_id: str) -> List[Tuple[str, str]]:
    """Extract (question, answer) pairs from the restaurant's FAQ document(s)."""
    docs = KnowledgeRepository.search_by_document_type(db, restaurant_id, "faq")
    pairs: List[Tuple[str, str]] = []
    for d in docs:
        for q, a in _QA_RE.findall(d.content or ""):
            q = q.strip()
            a = " ".join(a.split())  # collapse internal whitespace/newlines
            if q and a:
                pairs.append((q, a))
    return pairs


class FaqService:

    @staticmethod
    def answer(db: Session, restaurant_id: str, question: str) -> Optional[Dict[str, Any]]:
        """Return a curated FAQ answer for a confident match, else None."""
        q_tokens = _tokens(question)
        if len(q_tokens) < 2:
            return None

        pairs = _parse_faqs(db, restaurant_id)
        if not pairs:
            return None

        best_answer = None
        best_question = None
        best_score = 0.0
        best_shared = 0
        for faq_q, faq_a in pairs:
            faq_tokens = _tokens(faq_q)
            if not faq_tokens:
                continue
            shared = q_tokens & faq_tokens
            score = len(shared) / len(q_tokens | faq_tokens)  # Jaccard
            if score > best_score:
                best_score = score
                best_shared = len(shared)
                best_answer = faq_a
                best_question = faq_q

        if best_answer and best_score >= _MIN_SCORE and best_shared >= _MIN_SHARED:
            return {
                "answer": best_answer,
                "response_source": "FAQ Engine",
                "sources": [],
                "matched_question": best_question,
                "score": round(best_score, 2),
            }
        return None

    @staticmethod
    def list_faqs(db: Session, restaurant_id: str) -> List[Tuple[str, str]]:
        """Return the restaurant's curated (question, answer) pairs."""
        return _parse_faqs(db, restaurant_id)

    @staticmethod
    def add_faq(db: Session, token: str, restaurant_id: str, question: str, answer: str):
        """Train a new FAQ: append a Q/A pair to the restaurant's FAQ document
        (PRD §11 'train FAQs'). The FAQ engine reads the document live, so the
        new entry is answerable immediately (no re-embedding required)."""
        from backend.services.auth_service import AuthService
        from backend.repositories.knowledge_repository import KnowledgeRepository
        AuthService.validate_tenant_access(db, token, restaurant_id)
        q, a = question.strip(), answer.strip()
        if not q or not a:
            raise ValueError("Both a question and an answer are required.")

        docs = KnowledgeRepository.search_by_document_type(db, restaurant_id, "faq")
        if docs:
            doc = docs[0]
            n = len(re.findall(r'Q\d+', doc.content or "")) + 1
            new_content = (doc.content or "").rstrip() + f"\n\nQ{n}: {q}\nA{n}: {a}\n"
            return KnowledgeRepository.update(db, doc.id, {"content": new_content})
        return KnowledgeRepository.create(
            db, restaurant_id=restaurant_id, title="Frequently Asked Questions",
            content=f"FREQUENTLY ASKED QUESTIONS\n\nQ1: {q}\nA1: {a}\n", document_type="faq",
        )
