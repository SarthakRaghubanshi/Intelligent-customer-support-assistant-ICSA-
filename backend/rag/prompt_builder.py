import os
import sys
from typing import List, Dict, Any

# Setup sys.path to resolve other modules if run directly
current_file_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.dirname(current_file_dir) if "rag" in current_file_dir else current_file_dir
root_dir = os.path.dirname(backend_dir)
if backend_dir not in sys.path:
    sys.path.append(backend_dir)
if root_dir not in sys.path:
    sys.path.append(root_dir)

from backend.rag.retriever import retrieve_relevant_chunks

def build_rag_prompt(query: str, retrieved_chunks: List[Dict[str, Any]]) -> str:
    """
    Combines the query with system instructions and formatted context chunks
    exactly in the format required for the LLM input.
    
    Args:
        query (str): The customer's original query.
        retrieved_chunks (List[Dict[str, Any]]): List of chunk dictionaries containing
                                                 'content', 'source', and 'restaurant_id'.
                                                 
    Returns:
        str: The fully formatted RAG prompt.
    """
    # 3. Construct a structured prompt containing: System instructions, Context, and User Question
    
    # Header instructions
    system_instructions = (
        "You are a helpful customer support assistant for Pizza Paradise.\n\n"
        "Use ONLY the provided context to answer the user's question.\n\n"
        "If the answer cannot be found in the context, reply:\n\n"
        '"I could not find that information in the restaurant knowledge base."'
    )
    
    # 4. Context section formatting
    context_sections = []
    for idx, chunk in enumerate(retrieved_chunks):
        source = chunk.get("source", "unknown_source")
        content = chunk.get("content", "").strip()
        
        # Format chunk representation:
        # [Chunk 1]
        # Source: refund_policy.txt
        #
        # <chunk content>
        chunk_str = f"[Chunk {idx + 1}]\nSource: {source}\n\n{content}"
        context_sections.append(chunk_str)
        
    context_block = "\n\n".join(context_sections)
    
    # 4. & 5. Compile the final prompt string
    prompt = (
        f"{system_instructions}\n\n"
        "Context:\n\n"
        f"{context_block}\n\n"
        "User Question:\n\n"
        f"{query}\n\n"
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
        final_prompt = build_rag_prompt(test_query, chunks)
        
        # 4. Print the complete generated prompt
        print("\n=== GENERATED PROMPT ===")
        print(final_prompt)
        print("=========================")
        
    except Exception as err:
        print(f"Execution failed: {str(err)}", file=sys.stderr)
        sys.exit(1)
