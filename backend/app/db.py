from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    DATABASE_URL: str


settings = Settings()

engine: AsyncEngine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
)

# canonical sessionmaker (import this in tests)
async_session_maker = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    """Use this outside FastAPI dependency injection (tests, scripts, one-offs)."""
    async with async_session_maker() as session:
        yield session


# FastAPI dependency (unchanged semantics)
async def get_session() -> AsyncIterator[AsyncSession]:
    async with async_session_maker() as session:
        yield session
