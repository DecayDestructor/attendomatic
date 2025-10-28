from fastapi import FastAPI
from .config import settings
from backend.db.database import create_db_and_tables
from backend.db.models import *
from .routers import index, attendanceRouter, userRouter
from backend.adapters.telegram import (
    router as telegram_router,
)

app = FastAPI()


@app.on_event("startup")
async def on_startup():
    create_db_and_tables()
    print("Database and tables created!")


app.include_router(
    index.router,
    prefix="/index",
)

app.include_router(
    userRouter.router,
    prefix="/users",
)


app.include_router(
    attendanceRouter.router,
    prefix="/attendance",
)
app.include_router(telegram_router, prefix="/adapters/telegram")


@app.get("/")
async def index(name: str | None = None):
    if name:
        return {"message": f"Hello, {name}!"}
    return {"message": "Hello, World!"}
