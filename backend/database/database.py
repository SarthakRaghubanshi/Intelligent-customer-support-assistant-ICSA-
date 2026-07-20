import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import NullPool
from backend.core.config import Config

# Connect arguments (SQLite compatibility)
connect_args = {}
if Config.DATABASE_URL.startswith("sqlite"):
    connect_args["check_same_thread"] = False

_engine_kwargs = {"connect_args": connect_args, "pool_pre_ping": True}

# For FILE-based SQLite test databases, use NullPool so the underlying file
# handle is released as soon as a session is closed. Without this, Windows keeps
# the .db file locked (WinError 32) and a test's os.remove() teardown fails even
# though its assertions passed. Real dev/uat/prod DBs keep the default pool.
# Match on the DB FILENAME starting with "test" (e.g. test.db, test_auth.db) —
# a precise check that excludes innocuous paths like "latest.db" and never
# applies to ':memory:' (whose basename is ':memory:').
_is_test_sqlite = False
if Config.DATABASE_URL.startswith("sqlite"):
    _db_file = os.path.basename(Config.DATABASE_URL.replace("sqlite:///", "")).lower()
    _is_test_sqlite = _db_file.startswith("test")
if _is_test_sqlite:
    _engine_kwargs["poolclass"] = NullPool
    _engine_kwargs.pop("pool_pre_ping", None)  # not applicable to NullPool

# Create the SQLAlchemy engine
engine = create_engine(Config.DATABASE_URL, **_engine_kwargs)

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
