from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://storyvoice_user:storyvoice_password@localhost:5432/storyvoice_db")

# Attempt to connect to PostgreSQL to verify availability. Fall back to SQLite if it fails.
try:
    if DATABASE_URL.startswith("postgresql"):
        temp_engine = create_engine(DATABASE_URL, connect_args={"connect_timeout": 2})
        with temp_engine.connect() as conn:
            pass
        engine = temp_engine
        print("Successfully connected to PostgreSQL database.")
    else:
        raise ValueError("Non-PostgreSQL URL provided, using fallback.")
except Exception as e:
    print(f"PostgreSQL connection failed: {e}. Falling back to SQLite.")
    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "storyvoice.db")
    DATABASE_URL = f"sqlite:///{db_path}"
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

