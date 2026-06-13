from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from backend.core.config import Config

# Connect arguments (SQLite compatibility)
connect_args = {}
if Config.DATABASE_URL.startswith("sqlite"):
    connect_args["check_same_thread"] = False

# Create the SQLAlchemy engine
engine = create_engine(
    Config.DATABASE_URL, 
    connect_args=connect_args,
    pool_pre_ping=True  # Important for checking connection health
)

# Database Session local factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    """
    Generates a database session and closes it when complete.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
