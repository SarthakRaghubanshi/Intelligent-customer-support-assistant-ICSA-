import os
import sys
import time
import random
from typing import List
from dotenv import load_dotenv
import google.generativeai as genai
from langchain_core.embeddings import Embeddings
from backend.core.gemini_client import EMBED_MODEL

# Resolve root dir
current_file_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(os.path.dirname(current_file_dir))

# Load environment key
env_path = os.path.join(root_dir, ".env")
load_dotenv(dotenv_path=env_path)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

class GeminiEmbedder(Embeddings):
    """
    Central embedding generation service utilizing Google's models/gemini-embedding-2.
    Serves as the single source of truth for generating vector representations.
    Incorporates automatic retries and jitter to handle free-tier API rate limits.
    """
    def __init__(self, api_key: str = None):
        self.api_key = api_key or GEMINI_API_KEY
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY is not configured in environment or .env file.")
        genai.configure(api_key=self.api_key)

    def _sanitize_text(self, text: str) -> str:
        """
        Sanitizes empty or whitespace-only strings to a single space.
        """
        if not text or not text.strip():
            return " "
        return text

    def _call_with_retry(self, func, *args, **kwargs):
        """
        Executes a Gemini API call with exponential backoff retries for quota rate limits.
        """
        max_retries = 6
        base_delay = 3.0
        for attempt in range(max_retries):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                error_str = str(e).lower()
                if "429" in error_str or "quota" in error_str or "resource_exhausted" in error_str or "rate limit" in error_str:
                    if attempt == max_retries - 1:
                        raise e
                    delay = base_delay * (2 ** attempt) + random.uniform(0.1, 1.5)
                    print(f"Rate limit hit during embedding. Retrying in {delay:.2f}s (attempt {attempt + 1}/{max_retries})...", file=sys.stderr)
                    time.sleep(delay)
                else:
                    raise e

    def generate_embedding(self, text: str) -> List[float]:
        """
        Generates a single query embedding vector (task_type="retrieval_query").
        Sanitizes empty inputs to a single space.
        """
        sanitized_text = self._sanitize_text(text)
        try:
            response = self._call_with_retry(
                genai.embed_content,
                model=EMBED_MODEL,
                content=sanitized_text,
                task_type="retrieval_query"
            )
            return response["embedding"]
        except Exception as e:
            print(f"Error generating embedding: {str(e)}", file=sys.stderr)
            raise e

    def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """
        Generates batch document embedding vectors (task_type="retrieval_document").
        Sanitizes all list elements to a single space if empty.
        """
        if not texts:
            return []
            
        sanitized_texts = [self._sanitize_text(t) for t in texts]
        try:
            response = self._call_with_retry(
                genai.embed_content,
                model=EMBED_MODEL,
                content=sanitized_texts,
                task_type="retrieval_document"
            )
            return response["embedding"]
        except Exception as e:
            print(f"Error generating embeddings: {str(e)}", file=sys.stderr)
            raise e

    def validate_embedding_dimensions(self) -> int:
        """
        Determines the output dimension of the model dynamically.
        """
        vector = self.generate_embedding("dimension_check")
        return len(vector)

    # LangChain compatibility methods
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return self.generate_embeddings(texts)

    def embed_query(self, text: str) -> List[float]:
        return self.generate_embedding(text)
