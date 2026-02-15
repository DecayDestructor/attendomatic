"""
FastAPI application entry point.

Initializes the app, registers all routers, and ensures the database
tables are created on startup.
"""

from fastapi import FastAPI
from backend.config import settings
from backend.db.database import create_db_and_tables
from backend.routers import index, attendanceRouter, userRouter
from backend.adapters.telegram import router as telegram_router

app = FastAPI()


@app.on_event("startup")
async def on_startup():
    """Create all database tables (if they don't exist) when the server starts."""
    create_db_and_tables()
    print("Database and tables created!")


# --- Register routers with their URL prefixes ---
app.include_router(index.router, prefix="/index")
app.include_router(userRouter.router, prefix="/users")
app.include_router(attendanceRouter.router, prefix="/attendance")
app.include_router(telegram_router, prefix="/adapters/telegram")


@app.get("/")
async def index(name: str | None = None):
    """Root health-check endpoint."""
    if name:
        return {"message": f"Hello, {name}!"}
    return {"message": "Hello, World!"}
