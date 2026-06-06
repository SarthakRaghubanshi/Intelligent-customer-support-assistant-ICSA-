import os
import sys
from typing import List
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

def split_documents(documents: List[Document]) -> List[Document]:
    """
    Splits the provided list of documents into smaller text chunks.
    Preserves parent metadata (source, restaurant_id, etc.).
    
    Args:
        documents (List[Document]): A list of loaded LangChain Document objects.
        
    Returns:
        List[Document]: A list of chunked Document objects.
    """
    # 2. Use LangChain RecursiveCharacterTextSplitter
    # 4. Configure chunk_size = 1000, chunk_overlap = 200
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200
    )
    
    # Splits documents and automatically copies metadata
    chunks = splitter.split_documents(documents)
    return chunks

if __name__ == "__main__":
    # Resolve the data and backend directories dynamically
    current_file_dir = os.path.dirname(os.path.abspath(__file__))
    backend_dir = os.path.dirname(current_file_dir) if "rag" in current_file_dir else current_file_dir
    root_dir = os.path.dirname(backend_dir)
    
    # Import document loader from sibling file
    # Ensure root/backend is in python path
    if backend_dir not in sys.path:
        sys.path.append(backend_dir)
    if root_dir not in sys.path:
        sys.path.append(root_dir)
        
    from backend.rag.document_loader import load_restaurant_documents
    
    test_restaurant_id = "Restaurant_A"
    test_data_dir = os.path.join(root_dir, "data", test_restaurant_id)
    
    try:
        # Load the documents first
        docs = load_restaurant_documents(test_restaurant_id, test_data_dir)
        
        # 6. Print number of original documents
        print(f"Loaded {len(docs)} documents")
        
        # Split the documents
        chunks = split_documents(docs)
        
        # 6. Print number of generated chunks
        print(f"\nGenerated {len(chunks)} chunks")
        
        # 7. Print metadata for first few chunks (e.g., first 5 chunks)
        print("\nFirst few chunks details:")
        for idx, chunk in enumerate(chunks[:5]):
            print(f"\nChunk {idx + 1}:")
            # The metadata format specified is:
            # Source: refund_policy.txt
            # Restaurant: Restaurant_A
            print(f"Source: {chunk.metadata.get('source')}")
            print(f"Restaurant: {chunk.metadata.get('restaurant_id')}")
            
    except Exception as err:
        print(f"Execution failed: {str(err)}", file=sys.stderr)
        sys.exit(1)
