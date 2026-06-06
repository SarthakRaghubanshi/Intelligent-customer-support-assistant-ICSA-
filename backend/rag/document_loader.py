import os
import sys
from typing import List
from langchain_core.documents import Document
from langchain_community.document_loaders import TextLoader

def load_restaurant_documents(restaurant_id: str, data_dir: str) -> List[Document]:
    """
    Loads all .txt documents from the specified restaurant directory.
    Attaches source filename and restaurant_id to the document metadata.
    
    Args:
        restaurant_id (str): The unique identifier of the restaurant (e.g. 'Restaurant_A').
        data_dir (str): The absolute or relative path to the directory containing text files.
        
    Returns:
        List[Document]: A list of loaded LangChain Document objects.
    """
    documents = []
    
    if not os.path.exists(data_dir):
        raise FileNotFoundError(f"Data directory '{data_dir}' not found.")
        
    # Scan the directory for all files
    for filename in os.listdir(data_dir):
        if filename.endswith(".txt"):
            file_path = os.path.join(data_dir, filename)
            try:
                # Load text file using LangChain's TextLoader
                loader = TextLoader(file_path, encoding="utf-8")
                loaded_docs = loader.load()
                
                # Enrich metadata for each loaded document object
                for doc in loaded_docs:
                    doc.metadata["source"] = filename
                    doc.metadata["restaurant_id"] = restaurant_id
                    
                documents.extend(loaded_docs)
            except Exception as e:
                print(f"Error loading document {filename}: {str(e)}", file=sys.stderr)
                raise e
                
    return documents

if __name__ == "__main__":
    # Resolve the data directory for testing
    current_file_dir = os.path.dirname(os.path.abspath(__file__))
    backend_dir = os.path.dirname(current_file_dir) if "rag" in current_file_dir else current_file_dir
    root_dir = os.path.dirname(backend_dir)
    
    test_restaurant_id = "Restaurant_A"
    test_data_dir = os.path.join(root_dir, "data", test_restaurant_id)
    
    print(f"Resolving documents from: {test_data_dir}")
    
    try:
        docs = load_restaurant_documents(test_restaurant_id, test_data_dir)
        
        # 5. Print loaded document count
        print(f"\nSuccessfully loaded {len(docs)} document(s).")
        
        # 6. Print loaded filenames
        print("Loaded filenames:")
        for doc in docs:
            print(f" - {doc.metadata['source']} (Restaurant ID: {doc.metadata['restaurant_id']})")
            
    except Exception as err:
        print(f"Execution failed: {str(err)}", file=sys.stderr)
        sys.exit(1)
