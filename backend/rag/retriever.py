import os
import sys
from typing import List, Dict, Any

# Setup sys.path to find other modules if run directly
current_file_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.dirname(current_file_dir) if "rag" in current_file_dir else current_file_dir
root_dir = os.path.dirname(backend_dir)
if backend_dir not in sys.path:
    sys.path.append(backend_dir)
if root_dir not in sys.path:
    sys.path.append(root_dir)

from backend.rag.vector_store import load_vector_store

# NOTE: The retriever must not directly import or depend on GeminiEmbedder.
# Embedding generation logic belongs strictly beneath the vector store layer (vector_store.py).
# All query embedding resolution occurs dynamically within Chroma using the configured embedding function.

def retrieve_relevant_chunks(query: str, restaurant_id: str, k: int = 5) -> List[Dict[str, Any]]:
    """
    Retrieves the top k semantically relevant chunks for a user query from ChromaDB.
    Prints retrieval details in the terminal console, including Rank, Source, Restaurant ID,
    Similarity Score, and a 150-character Preview.
    
    Args:
        query (str): The search query from the user.
        restaurant_id (str): The unique identifier of the restaurant database to load.
        k (int): Number of chunks to retrieve.
        
    Returns:
        List[Dict[str, Any]]: A list of dictionaries representing the retrieved documents.
    """
    # 1. Resolve path to Chroma database
    persist_dir = os.path.join(root_dir, "data", "chroma_db", restaurant_id)
    
    # Check if persist directory exists to prevent empty db crashes
    if not os.path.exists(persist_dir):
        print(f"Warning: No persistent vector store found for restaurant {restaurant_id}. Returning empty results.")
        return []

    try:
        # 2. Load persistent ChromaDB
        db = load_vector_store(restaurant_id, persist_dir)
        
        # 4. Perform semantic similarity search with score
        results = db.similarity_search_with_score(query, k=k)
    except Exception as e:
        print(f"Warning: Failed to retrieve from vector store for restaurant {restaurant_id}: {str(e)}")
        return []
    
    # 6. Print retrieved chunks in terminal
    print(f"\nQuery: {query}")
    
    retrieved_chunks = []
    for idx, (doc, score) in enumerate(results):
        source = doc.metadata.get("source", "unknown_source")
        rest_id = doc.metadata.get("restaurant_id", restaurant_id)
        content = doc.page_content
        
        # Format preview text to first 150 characters
        preview = content[:150].strip()
        if len(content) > 150:
            preview += "..."
            
        # Print format requested by user:
        # Result #1
        # Source: refund_policy.txt
        # Restaurant: Restaurant_A
        # Score: 0.3214
        # Preview: Orders cancelled within 5 minutes...
        print(f"\nResult #{idx + 1}")
        print(f"Source: {source}")
        print(f"Restaurant: {rest_id}")
        print(f"Score: {score:.4f}")
        print(f"Preview: {preview}")
        
        # 5. Return dict representation
        retrieved_chunks.append({
            "content": content,
            "source": source,
            "restaurant_id": rest_id,
            "score": float(score)
        })
        
    print("\n" + "=" * 50)
    
    return retrieved_chunks

def retrieve_relevant_chunks_with_metadata(restaurant_id: str, query: str) -> List[Dict[str, Any]]:
    """
    Retrieves the relevant chunks for a user query from ChromaDB and returns them
    formatted with document_id, title, document_type, and content.
    """
    persist_dir = os.path.join(root_dir, "data", "chroma_db", restaurant_id)
    if not os.path.exists(persist_dir):
        return []

    try:
        db = load_vector_store(restaurant_id, persist_dir)
        results = db.similarity_search_with_score(query, k=5)
    except Exception as e:
        print(f"Warning: Failed to retrieve with metadata from vector store for restaurant {restaurant_id}: {str(e)}")
        return []

    retrieved_chunks = []
    for doc, score in results:
        retrieved_chunks.append({
            "content": doc.page_content,
            "document_id": doc.metadata.get("document_id"),
            "title": doc.metadata.get("source"),
            "document_type": doc.metadata.get("document_type"),
            # Distance score (lower = closer). Included so the RAG service does
            # not need a second embedding round-trip just to obtain scores.
            "score": float(score),
        })

    return retrieved_chunks

if __name__ == "__main__":
    test_restaurant_id = "Restaurant_A"
    
    # Test queries
    test_queries = [
        "What is your refund policy?",
        "Do you offer vegan pizza?",
        "What are your delivery charges?",
        "What are your pickup timings?"
    ]
    
    print("Starting Retrieval Layer Test...")
    print("=" * 50)
    
    try:
        for q in test_queries:
            retrieve_relevant_chunks(q, test_restaurant_id, k=5)
            
    except Exception as err:
        print(f"Execution failed: {str(err)}", file=sys.stderr)
        sys.exit(1)
