import asyncio
import pytest

from app.db import async_session_maker, engine
from app.seed import seed_minimal


# IMPORTANT: single loop for whole test session, prevents asyncpg pooled conns crossing loops
@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session", autouse=True)
async def _dispose_engine_after_tests():
    yield
    # ensure pool is cleaned up
    await engine.dispose()


@pytest.fixture()
async def session():
    async with async_session_maker() as s:
        yield s


@pytest.fixture(autouse=True)
async def reseed_db(session):
    await seed_minimal(session)
