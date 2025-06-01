from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator

from ..core.config import settings
from .models import Base # Import Base from your models.py

# SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db" # Example for SQLite
# SQLALCHEMY_DATABASE_URL = "postgresql://user:password@postgresserver/db" # Example for PostgreSQL

engine = create_engine(
    settings.DATABASE_URL,
    # connect_args are specific to SQLite. Remove if using other DBs.
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Dependency to get DB session
def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def create_db_and_tables():
    Base.metadata.create_all(bind=engine)