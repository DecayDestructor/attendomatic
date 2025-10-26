from typing import Generator, Annotated
from fastapi import Depends
from sqlmodel import Session, SQLModel, create_engine
from backend.config import settings

engine = create_engine(settings.PG_DB, echo=True)


def create_db_and_tables():
    SQLModel.metadata.create_all(engine)


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session
