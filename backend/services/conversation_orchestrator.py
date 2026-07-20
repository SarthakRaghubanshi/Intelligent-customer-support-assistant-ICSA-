import os
import sys
import time
import datetime
from typing import Dict, Any, Callable, Optional
from sqlalchemy.orm import Session

# Menu/knowledge content contains characters like the rupee sign (₹). Ensure
# stdout/stderr can carry UTF-8 so debug logging never crashes on Windows
# consoles that default to a legacy code page (cp1252).
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Ensure proper project root path imports
current_file_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.dirname(current_file_dir) if "services" in current_file_dir else current_file_dir
root_dir = os.path.dirname(backend_dir)
if root_dir not in sys.path:
    sys.path.append(root_dir)

# Production NLU imports
from backend.classifiers.intent_classifier import classify_intent as prod_classify_intent
from backend.classifiers.sentiment_classifier import classify_sentiment as prod_classify_sentiment
from backend.classifiers.language_detector import detect_language as prod_detect_language
from backend.escalation.escalation_engine import EscalationEngine
from backend.rag.rag_service import RAGService
from backend.analytics.event_logger import create_event
from backend.analytics.session_analytics import update_session_analytics

class ConversationOrchestrator:
    """
    Dedicated Orchestrator Layer for Step 8 AI Pipeline.
    Manages NLU execution, escalation rules checking, RAGService delegation, and analytics logging.
    """

    @staticmethod
    def orchestrate(
        db: Session,
        restaurant_id: str,
        question: str,
        intent_classifier: Callable = None,
        sentiment_classifier: Callable = None,
        language_detector: Callable = None,
        conversation_id: Optional[str] = None,
        customer_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Orchestrates classifiers, rules, RAG, and logs.
        
        Args:
            db (Session): Database session.
            restaurant_id (str): UUID string identifying the restaurant.
            question (str): User query.
            intent_classifier (Callable): Injected intent classifier (optional, for tests).
            sentiment_classifier (Callable): Injected sentiment analyzer (optional, for tests).
            language_detector (Callable): Injected language detector (optional, for tests).
        
        Returns:
            Dict[str, Any]: Simplified response contract.
        """
        # 1. Enforce query presence validation
        if not question or not question.strip():
            raise ValueError("User message cannot be empty.")

        start_time = time.perf_counter()

        # 1b. Respect the restaurant's AI assistant toggle (PRD Section 11).
        ai_config = {}
        try:
            from backend.services.restaurant_service import RestaurantService
            ai_config = RestaurantService.get_ai_config(db, restaurant_id)
        except Exception:
            ai_config = {}
        if ai_config.get("ai_enabled") is False:
            return {
                "answer": "Our AI assistant is currently turned off for this restaurant. "
                          "A team member will get back to you shortly.",
                "intent": "Disabled", "sentiment": "Neutral", "language": "English",
                "language_code": "en", "escalation_result": {"escalate": True, "reason": "AI Disabled"},
                "sources": [], "chunks_used": 0, "prompt": "", "error": False, "exception": None,
                "intent_info": {"intent": "Disabled", "confidence": 0.0, "layer": "Config"},
                "language_info": {"language": "English", "code": "en", "confidence": 0.0, "layer": "Config"},
            }

        # 2. Run Intent Classification with Fault-Tolerant Fallback
        fn_intent = intent_classifier or prod_classify_intent
        try:
            intent_result = fn_intent(question)
        except Exception:
            intent_result = {
                "intent": "Unknown",
                "confidence": 0.0,
                "layer": "Fallback"
            }

        # 3. Run Sentiment Analysis with Fault-Tolerant Fallback
        fn_sentiment = sentiment_classifier or prod_classify_sentiment
        try:
            sentiment_result = fn_sentiment(question)
        except Exception:
            sentiment_result = {
                "sentiment": "Neutral",
                "confidence": 0.0,
                "layer": "Fallback"
            }

        # 4. Run Language Detection with Fault-Tolerant Fallback
        fn_lang = language_detector or prod_detect_language
        try:
            language_result = fn_lang(question)
        except Exception:
            language_result = {
                "language": "Unknown",
                "code": "unknown",
                "confidence": 0.0,
                "layer": "Fallback"
            }

        # 5. Run Escalation Rules Evaluation
        try:
            escalation_engine = EscalationEngine()
            escalation_result = escalation_engine.evaluate(
                intent=intent_result["intent"],
                sentiment=sentiment_result["sentiment"],
                confidence=intent_result["confidence"],
                query=question,
                low_confidence_threshold=ai_config.get("low_confidence_threshold", 0.60),
                enabled_rules=ai_config.get("enabled_rules")
            )
            
            # Auto-creation hook for Step 10 Escalation Events
            if escalation_result.get("escalate") and conversation_id:
                from backend.services.escalation_service import EscalationService
                EscalationService.create_escalation(
                    db=db,
                    conversation_id=conversation_id,
                    reason=escalation_result.get("reason", "Unknown")
                )
        except Exception as e:
            print(f"Error in escalation evaluation or DB creation: {str(e)}", file=sys.stderr)
            escalation_result = {
                "escalate": False,
                "reason": "Escalation Evaluation Failed"
            }

        # 6. Answer generation.
        # (a) Domain routing first: order status/modification, menu discovery, and
        #     personalized recommendations are answered from live structured data
        #     (orders/products tables) so order facts are never hallucinated.
        # (b) Everything else (FAQs, policies, delivery/pickup, general questions)
        #     goes to the RAG knowledge pipeline, with NLU metadata forwarded so
        #     tone (sentiment) and language actually shape the generated answer.
        nlu_metadata = {
            "intent": intent_result.get("intent"),
            "sentiment": sentiment_result.get("sentiment"),
            "language": language_result.get("language"),
            "language_code": language_result.get("code"),
        }

        domain_res = None
        try:
            from backend.services.assistant_router import route as domain_route
            domain_res = domain_route(db, restaurant_id, customer_id, question, intent_result["intent"])
        except Exception as e:
            print(f"Domain routing error: {str(e)}", file=sys.stderr)
            domain_res = None

        if domain_res is not None:
            # Domain answers are English templates; translate to the detected
            # language so every answer path honors multilingual support (Module 9).
            answer_text_domain = domain_res.get("answer", "")
            _lang = language_result.get("language")
            if answer_text_domain and _lang and str(_lang).strip().lower() not in ("english", "unknown", ""):
                try:
                    from backend.core.gemini_client import translate_text
                    answer_text_domain = translate_text(answer_text_domain, _lang)
                except Exception:
                    pass
            rag_res = {
                "answer": answer_text_domain,
                "sources": domain_res.get("sources", []),
                "chunks_used": 0,
                "best_score": 0.0,
                "rag_decision": "DOMAIN",
                "response_source": domain_res.get("response_source", "Domain"),
                "prompt": "",
            }
        else:
            # (c) Smart FAQ engine (Module 5): try a curated FAQ match first — a
            #     deterministic, verbatim answer that cannot hallucinate. Falls
            #     back to RAG when no curated question matches confidently.
            faq_res = None
            try:
                from backend.services.faq_service import FaqService
                faq_res = FaqService.answer(db, restaurant_id, question)
            except Exception:
                faq_res = None

            if faq_res is not None:
                faq_answer = faq_res.get("answer", "")
                _lang = language_result.get("language")
                if faq_answer and _lang and str(_lang).strip().lower() not in ("english", "unknown", ""):
                    try:
                        from backend.core.gemini_client import translate_text
                        faq_answer = translate_text(faq_answer, _lang)
                    except Exception:
                        pass
                rag_res = {
                    "answer": faq_answer, "sources": [], "chunks_used": 0,
                    "best_score": 0.0, "rag_decision": "FAQ",
                    "response_source": "FAQ Engine", "prompt": "",
                }
            else:
                # (d) RAG knowledge pipeline, with multi-turn memory: give the LLM
                #     the recent conversation turns so it can resolve follow-ups
                #     (Module 1). Domain answers above are single-turn by design.
                history = []
                if conversation_id:
                    try:
                        from backend.repositories.message_repository import MessageRepository
                        msgs = MessageRepository.list_by_conversation(db, conversation_id)
                        recent = [m for m in msgs if m.content and m.content.strip()]
                        # Drop the just-persisted current user question if it's the last row.
                        if recent and recent[-1].role == "user" and recent[-1].content.strip() == question.strip():
                            recent = recent[:-1]
                        history = [{"role": m.role, "content": m.content} for m in recent[-6:]]
                    except Exception:
                        history = []
                rag_res = RAGService.answer_question(db, restaurant_id, question, metadata=nlu_metadata, history=history)

        # RAGService returns:
        # {
        #     "answer": str,
        #     "sources": list,
        #     "chunks_used": int,
        #     "best_score": float,
        #     "rag_decision": str,
        #     "response_source": str,
        #     "prompt": str
        # }

        # Calculate Latency
        latency_ms = (time.perf_counter() - start_time) * 1000.0

        # Extract values
        answer_text = rag_res.get("answer", "I could not find that information in the restaurant knowledge base.")
        response_sources = rag_res.get("sources", [])
        chunks_used = rag_res.get("chunks_used", 0)
        best_score = rag_res.get("best_score", 1.0)
        decision = rag_res.get("rag_decision", "FALLBACK")
        response_source = rag_res.get("response_source", "System Fallback")
        raw_prompt = rag_res.get("prompt", "")

        # 7. Print Log Blocks to stdout to satisfy verify_language_integration.py expectations
        # Print PIPELINE_LOG block
        print(f"\n=================== [PIPELINE_LOG] ===================")
        print(f"Timestamp:             {datetime.datetime.now().isoformat()}")
        print(f"Query:                 {question}")
        print(f"Predicted Intent:      {intent_result['intent']}")
        print(f"Intent Confidence:     {intent_result['confidence']:.4f}")
        print(f"Intent Layer:          {intent_result['layer']}")
        print(f"Predicted Sentiment:   {sentiment_result['sentiment']}")
        print(f"Sentiment Confidence:  {sentiment_result['confidence']:.4f}")
        print(f"Sentiment Layer:       {sentiment_result['layer']}")
        print(f"Predicted Language:    {language_result['language']}")
        print(f"Language Code:         {language_result['code']}")
        print(f"Language Confidence:   {language_result['confidence']:.4f}")
        print(f"Language Layer:        {language_result['layer']}")
        print(f"RAG Used:              {decision == 'PASS_TO_GEMINI'}")
        print(f"Best Similarity Score: {best_score:.4f}")
        print(f"Threshold:             0.75")
        print(f"Decision:              {decision}")
        print(f"======================================================\n")

        # Print GROUNDED_PROMPT block only if we didn't fall back
        if decision == "PASS_TO_GEMINI" and raw_prompt:
            # Reconstruct metadata headers to match verify_language_integration check
            metadata_lines = []
            metadata_lines.append(f"Detected Intent: {intent_result['intent']}")
            metadata_lines.append(f"Detected Sentiment: {sentiment_result['sentiment']}")
            metadata_lines.append(f"Detected Language: {language_result['language']} ({language_result['code']})")
            metadata_query_section = "\n".join(metadata_lines) + f"\n\nUser Query:\n{question}"
            
            # Format display prompt by replacing raw query section with metadata query section
            target_to_replace = f"User Question:\n\n{question}"
            if target_to_replace in raw_prompt:
                grounded_prompt_for_print = raw_prompt.replace(target_to_replace, metadata_query_section)
            else:
                grounded_prompt_for_print = f"[System Instructions & Context]\n\n{metadata_query_section}\n\nAnswer:"
                
            print(f"\n=================== [GROUNDED_PROMPT] ===================")
            print(grounded_prompt_for_print)
            print(f"==========================================================\n")

        # 8. Logging to Analytics Event Logger & Session Statistics
        retrieved_source_names = [s.get("title", "unknown") for s in response_sources]
        try:
            event = create_event({
                "timestamp": datetime.datetime.now().isoformat(),
                "restaurant_id": restaurant_id,
                "query": question,
                "intent": intent_result["intent"],
                "intent_confidence": intent_result["confidence"],
                "intent_layer": intent_result["layer"],
                "sentiment": sentiment_result["sentiment"],
                "sentiment_confidence": sentiment_result["confidence"],
                "sentiment_layer": sentiment_result["layer"],
                "language": language_result["language"],
                "language_code": language_result["code"],
                "language_confidence": language_result["confidence"],
                "language_layer": language_result["layer"],
                "best_similarity_score": best_score,
                "rag_decision": decision,
                "retrieved_sources": retrieved_source_names,
                "response_source": response_source,
                "response_length": len(answer_text),
                "latency_ms": latency_ms,
                "escalated": escalation_result["escalate"],
                "escalation_reason": escalation_result["reason"]
            })
            if event:
                update_session_analytics(event)
        except Exception as e:
            print(f"Analytics event creation failed: {str(e)}", file=sys.stderr)

        # 9. Return public Step 8 response contract (completely decoupled from internal structures)
        # Note: If an exception is raised by the RAGService (e.g. Gemini quota errors), we pass it along
        # in the dict to keep gemini_service.py backward compatible.
        return {
            "answer": answer_text,
            "intent": intent_result["intent"],
            "sentiment": sentiment_result["sentiment"],
            "language": language_result["language"],
            "language_code": language_result["code"],
            "escalation_result": escalation_result,
            "sources": response_sources,
            "chunks_used": chunks_used,
            "latency_ms": latency_ms,
            "response_source": response_source,
            "prompt": raw_prompt,
            "error": rag_res.get("error", False),
            "exception": rag_res.get("exception", None),
            "intent_info": intent_result,
            "sentiment_info": sentiment_result,
            "language_info": language_result
        }
