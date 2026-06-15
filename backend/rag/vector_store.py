import os
import sys
from typing import List
from dotenv import load_dotenv
from langchain_core.embeddings import Embeddings
from langchain_chroma import Chroma
import google.generativeai as genai

# Setup sys.path to find other modules if run directly
current_file_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.dirname(current_file_dir) if "rag" in current_file_dir else current_file_dir
root_dir = os.path.dirname(backend_dir)
if backend_dir not in sys.path:
    sys.path.append(backend_dir)
if root_dir not in sys.path:
    sys.path.append(root_dir)

# Load env variables from root folder
env_path = os.path.join(root_dir, ".env")
load_dotenv(dotenv_path=env_path)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

from backend.rag.document_loader import load_restaurant_documents
from backend.rag.text_splitter import split_documents

class GeminiCustomEmbeddings(Embeddings):
    """
    Custom LangChain Embeddings wrapper utilizing Google's models/gemini-embedding-2.
    """
    def __init__(self, api_key: str):
        self.api_key = api_key
        genai.configure(api_key=self.api_key)

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        try:
            response = genai.embed_content(
                model="models/gemini-embedding-2",
                content=texts,
                task_type="retrieval_document"
            )
            # Returns List[List[float]]
            return response["embedding"]
        except Exception as e:
            print(f"Error embedding documents: {str(e)}", file=sys.stderr)
            raise e

    def embed_query(self, text: str) -> List[float]:
        try:
            response = genai.embed_content(
                model="models/gemini-embedding-2",
                content=text,
                task_type="retrieval_query"
            )
            # Returns List[float]
            return response["embedding"]
        except Exception as e:
            print(f"Error embedding query: {str(e)}", file=sys.stderr)
            raise e

def load_vector_store(restaurant_id: str, persist_dir: str) -> Chroma:
    """
    Loads an existing persistent ChromaDB database.
    """
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY is not configured in .env file.")
        
    embeddings = GeminiCustomEmbeddings(GEMINI_API_KEY)
    
    # Load existing database
    db = Chroma(
        collection_name=f"restaurant_kb_{restaurant_id}",
        embedding_function=embeddings,
        persist_directory=persist_dir
    )
    return db

def create_vector_store(restaurant_id: str, data_dir: str, persist_dir: str) -> Chroma:
    """
    Checks if ChromaDB already exists. If so, loads it.
    Otherwise, loads docs, chunks them, embeds them, and saves to ChromaDB.
    """
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY is not configured in .env file.")
        
    embeddings = GeminiCustomEmbeddings(GEMINI_API_KEY)
    
    # Load or initialize vector store
    db = Chroma(
        collection_name=f"restaurant_kb_{restaurant_id}",
        embedding_function=embeddings,
        persist_directory=persist_dir
    )
    
    # Check if database contains vectors
    existing_docs = db.get()
    if existing_docs and existing_docs.get("ids"):
        # ChromaDB already populated - load from disk and do not rebuild
        print(f"Loaded existing database from {persist_dir}")
        num_vectors = len(existing_docs["ids"])
        print(f"Stored {num_vectors} vectors in ChromaDB")
        return db
        
    # Database is empty, start pipeline
    # 2. Load documents
    docs = load_restaurant_documents(restaurant_id, data_dir)
    print(f"Loaded {len(docs)} documents")
    
    # 3. Generate chunks
    chunks = split_documents(docs)
    print(f"Generated {len(chunks)} chunks")
    
    # 4. Generate embeddings and 5. Create persistent database
    print(f"Created embeddings for {len(chunks)} chunks")
    db.add_documents(chunks)
    
    num_vectors = len(db.get()["ids"])
    print(f"Stored {num_vectors} vectors in ChromaDB")
    
    return db

def add_document_to_vector_store(restaurant_id: str, doc_id: str, title: str, content: str, document_type: str) -> None:
    """
    Chunks, embeds, and adds a database document to the restaurant's ChromaDB collection.
    """
    from langchain_core.documents import Document
    from backend.rag.text_splitter import split_documents

    persist_dir = os.path.join(root_dir, "data", "chroma_db", restaurant_id)
    db = load_vector_store(restaurant_id, persist_dir)

    # Create LangChain Document
    metadata = {
        "source": title,
        "document_id": str(doc_id),
        "restaurant_id": restaurant_id,
        "document_type": document_type
    }
    raw_doc = Document(page_content=content, metadata=metadata)

    # Chunk the document
    chunks = split_documents([raw_doc])

    # Generate unique IDs for each chunk
    chunk_ids = [f"{doc_id}_chunk_{idx}" for idx in range(len(chunks))]

    # Add chunks to Chroma
    if chunks:
        db.add_documents(chunks, ids=chunk_ids)

def delete_document_from_vector_store(restaurant_id: str, doc_id: str) -> None:
    """
    Deletes all vector store chunks associated with the given document ID.
    """
    persist_dir = os.path.join(root_dir, "data", "chroma_db", restaurant_id)
    if not os.path.exists(persist_dir):
        return
        
    db = load_vector_store(restaurant_id, persist_dir)
    
    # Query for chunk IDs matching the document_id metadata
    result = db.get(where={"document_id": str(doc_id)})
    existing_ids = result.get("ids", [])
    
    if existing_ids:
        db.delete(ids=existing_ids)

def sync_restaurant_knowledge_base(db_session, restaurant_id: str) -> None:
    """
    Performs a full rebuild of the restaurant's ChromaDB collection.
    Loads all active KnowledgeDocuments from the database, chunks and embeds them.
    """
    from backend.repositories.knowledge_repository import KnowledgeRepository
    from langchain_core.documents import Document
    from backend.rag.text_splitter import split_documents
    
    persist_dir = os.path.join(root_dir, "data", "chroma_db", restaurant_id)
    db = load_vector_store(restaurant_id, persist_dir)
    
    # Clear all existing documents from Chroma collection using delete
    result = db.get()
    existing_ids = result.get("ids", [])
    if existing_ids:
        db.delete(ids=existing_ids)
        
    # Fetch all active documents for this restaurant from SQL
    db_docs = KnowledgeRepository.list_by_restaurant(db_session, restaurant_id)
    if not db_docs:
        return
        
    # Convert db models to LangChain Documents
    langchain_docs = []
    for db_doc in db_docs:
        metadata = {
            "source": db_doc.title,
            "document_id": str(db_doc.id),
            "restaurant_id": restaurant_id,
            "document_type": db_doc.document_type
        }
        langchain_docs.append(Document(page_content=db_doc.content, metadata=metadata))
        
    # Chunk all documents
    chunks = split_documents(langchain_docs)
    if not chunks:
        return
        
    # Generate IDs and add to store
    chunk_ids = []
    doc_chunk_counters = {}
    for chunk in chunks:
        doc_id = chunk.metadata["document_id"]
        idx = doc_chunk_counters.get(doc_id, 0)
        chunk_ids.append(f"{doc_id}_chunk_{idx}")
        doc_chunk_counters[doc_id] = idx + 1
        
    db.add_documents(chunks, ids=chunk_ids)


if __name__ == "__main__":
    test_restaurant_id = "Restaurant_A"
    test_data_dir = os.path.join(root_dir, "data", test_restaurant_id)
    test_persist_dir = os.path.join(root_dir, "data", "chroma_db", test_restaurant_id)
    
    # Standalone Testing
    try:
        # Clear existing test DB if any to test initial creation
        import shutil
        if os.path.exists(test_persist_dir):
            shutil.rmtree(test_persist_dir)
            
        print("--- Running first-time creation test ---")
        db = create_vector_store(test_restaurant_id, test_data_dir, test_persist_dir)
        
        print("\n--- Running second-time load test (no recreation) ---")
        db_loaded = create_vector_store(test_restaurant_id, test_data_dir, test_persist_dir)
        
        # Verify persistence is indeed working
        print(f"\nVerification check: Vector store has {len(db_loaded.get()['ids'])} documents stored.")
        
    except Exception as err:
        print(f"Execution failed: {str(err)}", file=sys.stderr)
        sys.exit(1)
