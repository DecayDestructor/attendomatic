"""
Database engine and session management.

Creates a SQLAlchemy engine from the PG_DB connection string and provides
a generator-based session dependency for FastAPI routes.
"""

from typing import Generator, Annotated
from fastapi import Depends
from sqlmodel import Session, SQLModel, create_engine
from backend.config import settings

# echo=True logs all SQL statements to stdout (useful for debugging)
engine = create_engine(settings.PG_DB, echo=True)


def create_db_and_tables():
    """Create all tables defined by SQLModel metadata if they don't already exist."""
    SQLModel.metadata.create_all(engine)


def get_session() -> Generator[Session, None, None]:
    """Yield a database session and automatically close it after use."""
    with Session(engine) as session:
        yield session
