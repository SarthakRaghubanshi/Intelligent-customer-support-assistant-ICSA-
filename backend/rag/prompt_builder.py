import os
import sys
from typing import List, Dict, Any, Optional

# Setup sys.path to resolve other modules if run directly
current_file_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.dirname(current_file_dir) if "rag" in current_file_dir else current_file_dir
root_dir = os.path.dirname(backend_dir)
if backend_dir not in sys.path:
    sys.path.append(backend_dir)
if root_dir not in sys.path:
    sys.path.append(root_dir)

from backend.rag.retriever import retrieve_relevant_chunks

TENANT_MAP = {
    "Restaurant_A": "Pizza Paradise",
    "Restaurant_B": "Burgers & Co",
    "Restaurant_C": "Sushi Zen"
}

def build_rag_prompt(
    restaurant_name: str,
    retrieved_chunks: List[Dict[str, Any]],
    question: str = None,
    **kwargs
) -> str:
    """
    Combines the query with system instructions, formatted context chunks,
    and optional metadata.
    
    Supports two signature formats:
    1. build_rag_prompt(restaurant_name, retrieved_chunks, question) -> Used by RAG Service
    2. build_rag_prompt(query, retrieved_chunks, restaurant_id=..., metadata=...) -> Used by existing tests
    """
    # Detect signature based on whether 'question' is passed
    if question is None:
        # Old signature format: build_rag_prompt(query, retrieved_chunks, restaurant_id=..., metadata=...)
        query_text = restaurant_name  # first parameter is actually the query
        restaurant_id = kwargs.get("restaurant_id", "Restaurant_A")
        resolved_name = TENANT_MAP.get(restaurant_id, "Pizza Paradise")
        metadata = kwargs.get("metadata")
    else:
        # New signature format: build_rag_prompt(restaurant_name, retrieved_chunks, question)
        query_text = question
        resolved_name = restaurant_name
        metadata = kwargs.get("metadata")

    intent = metadata.get("intent") if metadata else None
    sentiment = metadata.get("sentiment") if metadata else None
    language = metadata.get("language") if metadata else None
    language_code = metadata.get("language_code") if metadata else None
    history = kwargs.get("history") or []

    # Header instructions
    system_instructions = (
        f"You are a helpful customer support assistant for {resolved_name}.\n\n"
        "Use ONLY the provided context to answer the user's question.\n\n"
        "If the answer cannot be found in the context, reply:\n\n"
        '"I could not find that information in the restaurant knowledge base."'
    )
    
    if sentiment:
        system_instructions += (
            "\n\nAdjust your response tone to be appropriate for the detected sentiment "
            "(e.g., be empathetic for Negative sentiment, warm and appreciative for Positive sentiment). "
            "However, you must answer using ONLY the provided context. The sentiment must influence the response tone only; "
            "it must NOT override the retrieved facts, trigger refunds/escalations, or modify restaurant policies/business logic."
        )
    
    # Multilingual response: reply in the customer's detected language (PRD Module 9).
    if language and str(language).strip().lower() not in ("english", "unknown", ""):
        system_instructions += (
            f"\n\nThe customer wrote in {language}. Reply in {language} using natural, fluent phrasing, "
            "while still answering using ONLY the facts from the provided context."
        )

    # Multi-turn: use the recent conversation only to resolve follow-up references.
    if history:
        system_instructions += (
            "\n\nA recent conversation history is provided below. Use it ONLY to understand "
            "follow-up questions and references (e.g. \"what about the large one?\"). You must still "
            "answer using ONLY the knowledge context; never invent facts from the history."
        )

    # Strict hallucination prevention instructions
    system_instructions += (
        "\n\nOnly answer using the provided knowledge. Do not invent, extrapolate, or hallucinate "
        "any details, including menu items, prices, policies, opening hours, or restaurant information."
    )

    # Context section formatting
    context_sections = []
    for idx, chunk in enumerate(retrieved_chunks):
        source = chunk.get("title") or chunk.get("source") or "unknown_source"
        content = chunk.get("content", "").strip()
        doc_type = chunk.get("document_type") or "other"
        
        # Format chunk representation
        chunk_str = f"[Chunk {idx + 1}]\nSource: {source} (Type: {doc_type})\n\n{content}"
        context_sections.append(chunk_str)
        
    context_block = "\n\n".join(context_sections)
    
    # Format the user query section based on presence of metadata
    metadata_lines = []
    if intent:
        metadata_lines.append(f"Detected Intent: {intent}")
    if sentiment:
        metadata_lines.append(f"Detected Sentiment: {sentiment}")
    if language and language_code:
        metadata_lines.append(f"Detected Language: {language} ({language_code})")

    if metadata_lines:
        query_section = "\n".join(metadata_lines) + f"\n\nUser Query:\n{query_text}"
    else:
        query_section = f"User Question:\n\n{query_text}"
        
    # Recent conversation turns (multi-turn memory)
    history_block = ""
    if history:
        turns = []
        for m in history:
            role = "Customer" if (m.get("role") == "user") else "Assistant"
            content = (m.get("content") or "").strip()
            if content:
                turns.append(f"{role}: {content}")
        if turns:
            history_block = "Recent conversation:\n" + "\n".join(turns) + "\n\n"

    # Compile the final prompt string
    prompt = (
        f"{system_instructions}\n\n"
        "Context:\n\n"
        f"{context_block}\n\n"
        f"{history_block}"
        f"{query_section}\n\n"
        "Answer:"
    )
    
    return prompt


if __name__ == "__main__":
    test_restaurant_id = "Restaurant_A"
    test_query = "What is your refund policy?"
    
    print("Starting Prompt Builder Layer Test...")
    print("=" * 50)
    
    try:
        # 1. Retrieve the chunks
        chunks = retrieve_relevant_chunks(test_query, test_restaurant_id, k=5)
        
        # 3. Pass retrieved chunks to build_rag_prompt
        final_prompt = build_rag_prompt(test_query, chunks, restaurant_id=test_restaurant_id)
        
        # 4. Print the complete generated prompt
        print("\n=== GENERATED PROMPT ===")
        print(final_prompt)
        print("=========================")
        
    except Exception as err:
        print(f"Execution failed: {str(err)}", file=sys.stderr)
        sys.exit(1)
