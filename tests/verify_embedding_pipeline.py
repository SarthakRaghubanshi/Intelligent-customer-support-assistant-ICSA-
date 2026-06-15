import os
import sys
import shutil

# Ensure project root is in the path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.append(project_root)

# Force a distinct test DB for validation
test_db_path = os.path.join(project_root, "data", "test_kb_embeddings_saas.db")
os.environ["DATABASE_URL"] = f"sqlite:///{test_db_path}"

# Clean test db file if it already exists
if os.path.exists(test_db_path):
    os.remove(test_db_path)

from backend.database.database import engine, Base, SessionLocal
from backend.repositories.restaurant_repository import RestaurantRepository
from backend.rag.embedder import GeminiEmbedder
from backend.rag.vector_store import load_vector_store, create_vector_store
from backend.rag.retriever import retrieve_relevant_chunks

def run_embedding_pipeline_tests():
    print("=" * 80)
    print("RUNNING RESTAURANT EMBEDDING PIPELINE VERIFICATION")
    print("=" * 80)

    # Initialize Embedder instance
    print("Initializing GeminiEmbedder...")
    embedder = GeminiEmbedder()

    # 1. Single Embedding Generation
    print("\n1. Testing Single Embedding Generation...")
    vector = embedder.generate_embedding("Pizza Margherita")
    assert isinstance(vector, list)
    assert len(vector) > 0
    assert all(isinstance(val, float) for val in vector)
    print(f"✓ Single embedding generated successfully (dim = {len(vector)}).")

    # 2. Batch Embedding Generation
    print("\n2. Testing Batch Embedding Generation...")
    texts = ["Cheese Pizza", "Pepperoni Crust", "Garlic Bread"]
    vectors = embedder.generate_embeddings(texts)
    assert isinstance(vectors, list)
    assert len(vectors) == len(texts)
    for v in vectors:
        assert isinstance(v, list)
        assert len(v) == len(vector)
    print("✓ Batch embeddings generated successfully.")

    # 3. Dynamic Dimension Check
    print("\n3. Testing Dynamic Dimension Verification...")
    dynamic_dim = embedder.validate_embedding_dimensions()
    assert dynamic_dim == len(vector), f"Dimension mismatch: dynamic is {dynamic_dim}, single is {len(vector)}"
    print(f"✓ Dynamic dimension verification passed (dim = {dynamic_dim}).")

    # 4. Empty/Whitespace String Sanitization
    print("\n4. Testing Empty & Whitespace String Sanitization...")
    # Empty string should resolve identical to single space " "
    vector_empty = embedder.generate_embedding("")
    vector_space = embedder.generate_embedding(" ")
    vector_whitespace = embedder.generate_embedding("   ")
    
    # Assert they are equal
    assert vector_empty == vector_space, "Failed: Empty string did not map to single space vector."
    assert vector_whitespace == vector_space, "Failed: Whitespace string did not map to single space vector."
    print("✓ Empty and whitespace string inputs correctly map to single-space embeddings (no zero-vectors).")

    # 5. Long Text Handling
    print("\n5. Testing Long Text Handling...")
    long_text = "This is a very long text paragraph designed to evaluate the embedder's ability to handle longer strings. " * 30
    vector_long = embedder.generate_embedding(long_text)
    assert len(vector_long) == dynamic_dim
    print("✓ Long text embedded successfully.")

    # 6. Vector Store & Fail-Fast Dimension Mismatch Validation
    print("\n6. Testing Vector Store Integration & Fail-Fast Verification...")
    
    # Setup test DB tables
    Base.metadata.create_all(bind=engine)
    db_session = SessionLocal()
    
    test_restaurant = RestaurantRepository.create(db_session, name="Emb Test Restaurant")
    persist_dir = os.path.join(project_root, "data", "chroma_db", test_restaurant.id)
    
    if os.path.exists(persist_dir):
        shutil.rmtree(persist_dir)
        
    try:
        # Create store initially (will populate embeddings function)
        print("Creating store and inserting first documents...")
        from langchain_core.documents import Document
        from backend.rag.vector_store import Chroma
        
        db = create_vector_store(test_restaurant.id, os.path.join(project_root, "data", "Restaurant_A"), persist_dir)
        assert db is not None
        print("✓ Vector store created with GeminiEmbedder.")

        # Simulate dimension mismatch: mock Chroma's get to return a vector of size 512
        original_get = db.get
        def mock_get(*args, **kwargs):
            if "include" in kwargs and "embeddings" in kwargs["include"]:
                return {"embeddings": [[1.0] * 512]}
            return original_get(*args, **kwargs)
            
        db.get = mock_get
        
        # Override the vector_store.py load function's local get to check if it throws ValueError
        # To do this safely, we can inspect if loading again with the mocked db throws an error
        # Let's verify by checking our load_vector_store method call with a mock
        print("Verifying fail-fast dimension check...")
        
        # Test custom validation
        try:
            # We mock the loaded db get method inside load_vector_store to return 512 dimension
            import backend.rag.vector_store
            original_chroma = backend.rag.vector_store.Chroma
            
            class MockChroma(original_chroma):
                def get(self, *args, **kwargs):
                    if "include" in kwargs and "embeddings" in kwargs["include"]:
                        return {"embeddings": [[1.0] * 512]}
                    return super().get(*args, **kwargs)
            
            backend.rag.vector_store.Chroma = MockChroma
            try:
                load_vector_store(test_restaurant.id, persist_dir)
                assert False, "Failed: Did not throw error on dimension mismatch"
            except ValueError as e:
                print(f"✓ Fail-fast dimension validation threw ValueError as expected: {e}")
            finally:
                backend.rag.vector_store.Chroma = original_chroma
        except Exception as e:
            print(f"Error during MockChroma testing: {e}")
            raise e

        # 7. Retrieval Integration
        print("\n7. Testing Retrieval Integration...")
        # Create a new restaurant to bypass Chroma's in-memory instance caching of the first collection
        valid_restaurant = RestaurantRepository.create(db_session, name="Valid Emb Test Restaurant")
        valid_persist_dir = os.path.join(project_root, "data", "chroma_db", valid_restaurant.id)
        
        if os.path.exists(valid_persist_dir):
            shutil.rmtree(valid_persist_dir)
            
        db_valid = create_vector_store(valid_restaurant.id, os.path.join(project_root, "data", "Restaurant_A"), valid_persist_dir)
        
        chunks = retrieve_relevant_chunks("vegan pizza", valid_restaurant.id, k=1)
        assert len(chunks) > 0
        print("✓ RAG retrieval successfully returned matches using decoupled GeminiEmbedder.")
        
        # Clean up valid_persist_dir
        if os.path.exists(valid_persist_dir):
            shutil.rmtree(valid_persist_dir)

    finally:
        db_session.close()
        # Clean up database files and folder
        if os.path.exists(test_db_path):
            os.remove(test_db_path)
        if os.path.exists(persist_dir):
            shutil.rmtree(persist_dir)

    print("\n✓ ALL EMBEDDING PIPELINE VERIFICATION TESTS PASSED SUCCESSFULLY!")
    print("=" * 80)
    sys.exit(0)

if __name__ == "__main__":
    run_embedding_pipeline_tests()
