import os
from typing import Dict, Any, List
from sqlalchemy.orm import Session
from dotenv import load_dotenv
import google.generativeai as genai

from backend.core.tenant import verify_restaurant_active
from backend.repositories.restaurant_repository import RestaurantRepository
from backend.rag.retriever import retrieve_relevant_chunks_with_metadata
from backend.rag.prompt_builder import build_rag_prompt

# Resolve root dir and load env
current_file_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(os.path.dirname(current_file_dir))
env_path = os.path.join(root_dir, ".env")
load_dotenv(dotenv_path=env_path)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

class RAGService:
    @staticmethod
    def answer_question(db: Session, restaurant_id: str, question: str) -> Dict[str, Any]:
        """
        Connects retrieval, prompt building, and LLM text generation into a
        tenant-aware pipeline with strict hallucination prevention.
        """
        # 1. Verify restaurant is active (raises ValueError if inactive or deleted)
        verify_restaurant_active(db, restaurant_id)

        # 2. Retrieve relevant chunks with metadata
        retrieved_chunks = retrieve_relevant_chunks_with_metadata(restaurant_id, question)

        # 5. Empty Knowledge Base Handling - Immediately return fallback
        if not retrieved_chunks:
            return {
                "answer": "I could not find that information in the restaurant knowledge base.",
                "sources": [],
                "chunks_used": 0
            }

        # 3. Retrieve restaurant metadata using RestaurantRepository
        restaurant = RestaurantRepository.get_by_id(db, restaurant_id)
        if not restaurant:
            raise ValueError("Restaurant is inactive or deleted")

        # 4. Build prompt
        prompt = build_rag_prompt(restaurant.name, retrieved_chunks, question)

        # 6. Gemini Generation & Failure Handling
        if not GEMINI_API_KEY:
            return {
                "answer": "The knowledge assistant is temporarily unavailable.",
                "sources": [],
                "chunks_used": 0,
                "error": True
            }

        try:
            genai.configure(api_key=GEMINI_API_KEY)
            model = genai.GenerativeModel("gemini-2.5-flash")
            response = model.generate_content(prompt)
            if not response or not response.text:
                raise RuntimeError("Empty response from Gemini API.")
            answer_text = response.text
        except Exception as e:
            # Handle rate-limiting, API key errors, quotas, etc. gracefully
            print(f"Error during RAG Service Gemini call: {str(e)}")
            return {
                "answer": "The knowledge assistant is temporarily unavailable.",
                "sources": [],
                "chunks_used": 0,
                "error": True
            }

        # 7. Source Deduplication
        seen_doc_ids = set()
        deduplicated_sources = []
        for chunk in retrieved_chunks:
            doc_id = chunk.get("document_id")
            if doc_id and doc_id not in seen_doc_ids:
                seen_doc_ids.add(doc_id)
                deduplicated_sources.append({
                    "document_id": doc_id,
                    "title": chunk.get("title") or chunk.get("source") or "Unknown Document",
                    "document_type": chunk.get("document_type") or "other"
                })

        return {
            "answer": answer_text.strip(),
            "sources": deduplicated_sources,
            "chunks_used": len(retrieved_chunks)
        }
