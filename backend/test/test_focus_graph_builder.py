import pytest
from sqlalchemy import select

# Adjust imports
from app.db import session_scope
from app.seed import seed_minimal
from app.models import AbstractNode
from app.services.graph_focus import build_focus_graph  # <-- whatever your module is


pytestmark = pytest.mark.asyncio


async def _id(slug: str) -> str:
    async with session_scope() as session:
        a = (await session.execute(select(AbstractNode).where(AbstractNode.slug == slug))).scalar_one()
        return str(a.id)


def _slugs(graph) -> set[str]:
    return {n.slug for n in graph.abstract_nodes}  # pydantic models


async def test_physics_focus_contains_fourier_and_has_boundary_hints() -> None:
    async with session_scope() as session:
        await seed_minimal(session)

    async with session_scope() as session:
        physics_id = await _id("physics")
        g = await build_focus_graph(session=session, focus_abstract_id=physics_id)

        slugs = _slugs(g)
        assert "fourier-transform" in slugs
        assert len(g.boundary_hints) > 0
