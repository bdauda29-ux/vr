import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

DB_URL = os.getenv("DATABASE_URL", "sqlite:///vss.db")

# Fix for SQLAlchemy requiring 'postgresql://' instead of 'postgres://'
if DB_URL and DB_URL.startswith("postgres://"):
    DB_URL = DB_URL.replace("postgres://", "postgresql://", 1)

# Vercel Read-Only File System Fix for SQLite
if DB_URL.startswith("sqlite") and os.environ.get("VERCEL"):
    # On Vercel, we can only write to /tmp
    # This is ephemeral and data will be lost on restart, but it allows the app to run
    DB_URL = "sqlite:////tmp/vss.db"

connect_args = {"check_same_thread": False} if DB_URL.startswith("sqlite") else {}
engine = create_engine(DB_URL, future=True, echo=False, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
