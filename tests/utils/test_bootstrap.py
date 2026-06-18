import os
import sys
import unittest.mock as mock
import re
import random
import uuid
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import google.generativeai as genai

# Ensure project root is in the Python path
current_file_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_file_dir))
if project_root not in sys.path:
    sys.path.append(project_root)

from backend.database.database import Base
from backend.repositories.restaurant_repository import RestaurantRepository
from backend.models.restaurant import Restaurant

# Stop words to filter out before generating semantic representation
STOP_WORDS = {
    "the", "a", "an", "and", "or", "but", "is", "are", "was", "were", 
    "to", "of", "in", "on", "at", "for", "with", "about", "what", "where", 
    "how", "why", "who", "whom", "which", "this", "that", "these", "those", 
    "it", "its", "they", "them", "their", "his", "her", "you", "your", 
    "me", "my", "we", "our", "us"
}

CATEGORIES = {
    "delivery": ["delivery", "deliver", "charge", "charges", "fee", "fees", "cost", "costs", "shipping", "zone", "address"],
    "refund": ["refund", "refunds", "cancel", "cancellation", "cancellations", "return", "money", "pay", "order", "late", "cold", "complaint"],
    "menu": ["menu", "pizza", "pizzas", "margherita", "royale", "price", "prices", "topp", "toppings", "sauce", "sauces", "cheese", "cheeses", "food", "eat", "dough", "crust", "recipe", "recipes", "pepperoni", "nutella", "cake", "burger", "burgers", "mustard", "mayo", "relish", "cayenne", "pepper"],
    "hours": ["hour", "hours", "time", "times", "open", "close", "weekday", "weekdays", "weekend", "weekends", "timing", "timings", "schedule", "business", "am", "pm", "lobby", "counter", "pickup", "pickups", "curbside", "park", "parking"]
}

def text_to_words(text: str) -> list:
    """Tokenizes a string into alphanumeric words."""
    if not text:
        return []
    return re.findall(r"\b[a-z0-9]+\b", text.lower())

def word_to_vector(word: str, dim: int = 768) -> list:
    """Generates a stable, reproducible random vector for a single word."""
    rng = random.Random(word)
    return [rng.uniform(-1.0, 1.0) for _ in range(dim)]

def generate_semantic_vector(text: str, dim: int = 768) -> list:
    """
    Generates a deterministic vector using category keyword projection.
    Similar texts matching the same operational category will be clustered closely,
    while unrelated queries (out-of-scope) will be placed far apart.
    """
    words = text_to_words(text)
    
    # Check category matches
    matched_categories = []
    for cat, keywords in CATEGORIES.items():
        if any(kw in words for kw in keywords):
            matched_categories.append(cat)
            
    vector = [0.0] * dim
    
    # Sum matched category vectors with high weight
    if matched_categories:
        for cat in matched_categories:
            cat_vec = word_to_vector(cat, dim)
            for i in range(dim):
                vector[i] += cat_vec[i] * 1.5
                
    # Add text-specific projection to ensure unique inputs have unique vectors
    text_seed = text.strip().lower()
    rng = random.Random(text_seed)
    text_vec = [rng.uniform(-1.0, 1.0) for _ in range(dim)]
    mag_text = sum(x**2 for x in text_vec) ** 0.5
    if mag_text > 0:
        text_vec = [x / mag_text for x in text_vec]
        
    for i in range(dim):
        vector[i] += text_vec[i] * 0.2
        
    # Normalize final vector to unit length
    magnitude = sum(x**2 for x in vector) ** 0.5
    if magnitude > 0:
        return [x / magnitude for x in vector]
    return [0.1] * dim

# Global monkey-patch of embed_content to avoid slow network/quota issues during testing
def mock_embed_content(*args, **kwargs):
    # Determine the content passed to embed
    content = kwargs.get("content")
    if content is None:
        if len(args) > 1:
            content = args[1]
        elif len(args) == 1:
            content = args[0]
            
    # Models have dynamic dimensions, gemini-embedding-2 is 768
    dim = 768
    if isinstance(content, list):
        return {"embedding": [generate_semantic_vector(str(item), dim) for item in content]}
    else:
        return {"embedding": generate_semantic_vector(str(content), dim)}

# Apply monkey patch
genai.embed_content = mock_embed_content

def bootstrap_test_database(db_url: str = None) -> sessionmaker:
    """
    Initializes a test database, creates all tables, and returns a session factory.
    Uses sqlite in-memory by default if no db_url is provided.
    """
    if not db_url:
        db_url = "sqlite:///:memory:"
        
    connect_args = {}
    if db_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
        
    engine = create_engine(db_url, connect_args=connect_args)
    Base.metadata.create_all(bind=engine)
    
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)

def bootstrap_restaurant(db, restaurant_id: str, name: str):
    """
    Seeds a specific restaurant in the database if it doesn't exist.
    """
    existing = RestaurantRepository.get_by_id(db, restaurant_id)
    if not existing:
        restaurant = Restaurant(id=restaurant_id, name=name.strip())
        db.add(restaurant)
        db.commit()
        db.refresh(restaurant)
        return restaurant
    return existing

def bootstrap_default_test_data(db):
    """
    Seeds default test data, including Restaurant_A, required for backward-compatible tests.
    """
    # 1. Seed Restaurant_A
    bootstrap_restaurant(db, "Restaurant_A", "Restaurant_A")
    
    # 2. Seed default knowledge documents for Restaurant_A
    from backend.models.knowledge_document import KnowledgeDocument
    
    existing_count = db.query(KnowledgeDocument).filter(
        KnowledgeDocument.restaurant_id == "Restaurant_A",
        KnowledgeDocument.deleted_at.is_(None)
    ).count()
    
    if existing_count == 0:
        import shutil
        chroma_dir = os.path.join(project_root, "data", "chroma_db", "Restaurant_A")
        if os.path.exists(chroma_dir):
            try:
                shutil.rmtree(chroma_dir)
            except Exception:
                pass
                
        import glob
        doc_dir = os.path.join(project_root, "data", "Restaurant_A")
        if os.path.exists(doc_dir):
            file_paths = glob.glob(os.path.join(doc_dir, "*.txt"))
            for path in file_paths:
                filename = os.path.basename(path)
                title = filename
                
                # Determine document type based on filename
                doc_type = "other"
                for t in ["menu", "faq", "refund_policy", "delivery_policy", "business_hours"]:
                    if t in filename:
                        doc_type = t
                        break
                        
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()
                    
                doc_id = str(uuid.uuid4())
                doc = KnowledgeDocument(
                    id=doc_id,
                    restaurant_id="Restaurant_A",
                    title=title,
                    content=content,
                    document_type=doc_type
                )
                db.add(doc)
            db.commit()
            
            # Sync vector store for Restaurant_A using the new semantic mock embeddings
            from backend.rag.vector_store import sync_restaurant_knowledge_base
            sync_restaurant_knowledge_base(db, "Restaurant_A")

