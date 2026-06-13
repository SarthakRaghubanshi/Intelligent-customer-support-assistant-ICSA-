import os
from dotenv import load_dotenv

# Load environment variables from .env if present
load_dotenv()

class Config:
    # Fallback to local sqlite database path if DATABASE_URL is not set
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///data/saas.db")
    
    # Ensure data directory exists if using SQLite
    if DATABASE_URL.startswith("sqlite:///"):
        # Extract relative path (data/saas.db)
        db_path = DATABASE_URL.replace("sqlite:///", "")
        db_dir = os.path.dirname(db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)
