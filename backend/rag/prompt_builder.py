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
    "Restaurant_A": "Pizza Paradise"
}

def build_rag_prompt(
    query: str,
    retrieved_chunks: List[Dict[str, Any]],
    restaurant_id: str = "Restaurant_A",
    metadata: Optional[Dict[str, Any]] = None
) -> str:
    """
    Combines the query with system instructions, formatted context chunks,
    and optional metadata (such as intent and sentiment).
    
    Args:
        query (str): The customer's original query.
        retrieved_chunks (List[Dict[str, Any]]): List of chunk dictionaries containing
                                                 'content', 'source', and 'restaurant_id'.
        restaurant_id (str): The unique identifier of the restaurant.
        metadata (Optional[Dict[str, Any]]): Optional dictionary containing 'intent' and 'sentiment'.
                                                 
    Returns:
        str: The fully formatted RAG prompt.
    """
    intent = metadata.get("intent") if metadata else None
    sentiment = metadata.get("sentiment") if metadata else None
    language = metadata.get("language") if metadata else None
    language_code = metadata.get("language_code") if metadata else None

    # Resolve brand name from mapping
    brand_name = TENANT_MAP.get(restaurant_id, "Pizza Paradise")

    # Header instructions
    system_instructions = (
        f"You are a helpful customer support assistant for {brand_name}.\n\n"
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
    
    # Context section formatting
    context_sections = []
    for idx, chunk in enumerate(retrieved_chunks):
        source = chunk.get("source", "unknown_source")
        content = chunk.get("content", "").strip()
        
        # Format chunk representation
        chunk_str = f"[Chunk {idx + 1}]\nSource: {source}\n\n{content}"
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
        query_section = "\n".join(metadata_lines) + f"\n\nUser Query:\n{query}"
    else:
        query_section = f"User Question:\n\n{query}"
        
    # Compile the final prompt string
    prompt = (
        f"{system_instructions}\n\n"
        "Context:\n\n"
        f"{context_block}\n\n"
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
