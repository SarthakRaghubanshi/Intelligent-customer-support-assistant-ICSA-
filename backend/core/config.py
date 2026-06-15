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

    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "fallback_local_secret_key_for_development_purposes_only_123456")
    JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))

