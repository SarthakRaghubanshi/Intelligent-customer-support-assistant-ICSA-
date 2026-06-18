import sys
import os

# Set Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(current_dir)
if root_dir not in sys.path:
    sys.path.append(root_dir)

from backend.gemini_service import generate_response
from tests.utils import test_bootstrap
from backend.rag.prompt_builder import build_rag_prompt
from backend.rag.retriever import retrieve_relevant_chunks

def run_tests():
    test_queries = [
        "My pizza arrived cold.",
        "Excellent service!",
        "What are your opening hours?"
    ]
    
    print("=" * 80)
    print("RUNNING PIPELINE INTEGRATION VERIFICATION")
    print("=" * 80)
    
    for q in test_queries:
        print(f"\n---> Testing Query: '{q}'")
        try:
            response = generate_response(q)
            print(f"Chatbot Response: {response}")
        except Exception as e:
            print(f"Chatbot raised exception (expected if Gemini API rate-limited): {str(e)}")
            
    print("\n" + "=" * 80)
    print("GENERATING SAMPLE ENRICHED PROMPT")
    print("=" * 80)
    
    sample_query = "My pizza arrived cold and late."
    metadata = {
        "intent": "Complaint",
        "sentiment": "Negative"
    }
    try:
        # Retrieve fewer chunks for readability of the sample prompt
        chunks = retrieve_relevant_chunks(sample_query, "Restaurant_A", k=2)
        prompt = build_rag_prompt(sample_query, chunks, metadata=metadata)
        print(prompt)
    except Exception as e:
        print(f"Failed to generate sample prompt: {str(e)}")
        
    print("=" * 80)

if __name__ == "__main__":
    run_tests()
