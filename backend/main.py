from typing import Union
from teleapi.httpx_transport import httpx_teleapi_factory
from fastapi import FastAPI
from .config import settings
from backend.db.database import create_db_and_tables
from backend.db.models import *
from .routers import index, attendanceRouter, userRouter
from backend.adapters.telegram import (
    set_webhook,
    cleanup_bot,
    router as telegram_router,
)

app = FastAPI()


@app.on_event("startup")
async def on_startup():
    create_db_and_tables()
    print("Database and tables created!")
    webhook_url = settings.TELEGRAM_WEBHOOK_URL
    await set_webhook(webhook_url)


@app.on_event("shutdown")
async def on_shutdown():
    await cleanup_bot()


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
