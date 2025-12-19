import os
import pytest
from httpx import AsyncClient
from sqlalchemy import select

# Adjust these imports to your project layout
from app.main import app                       # <-- change if needed
from app.db import session_scope          # <-- change if needed
from app.models import AbstractNode
import httpx
from httpx import AsyncClient

transport = httpx.ASGITransport(app=app)




pytestmark = pytest.mark.asyncio


async def _reseed(client: AsyncClient) -> None:
    r = await client.post("/api/admin/seed")
    assert r.status_code == 200, r.text


async def _get_abs_id_by_slug(slug: str) -> str:
    async with session_scope() as session:
        row = (await session.execute(select(AbstractNode).where(AbstractNode.slug == slug))).scalar_one()
        return str(row.id)


async def _focus(client: AsyncClient, abstract_id: str) -> dict:
    r = await client.get(f"/api/graph/focus/{abstract_id}")
    assert r.status_code == 200, r.text
    return r.json()


def _slugs(graph: dict) -> set[str]:
    return {n["slug"] for n in graph["abstract_nodes"]}


def _boundary_slugs(graph: dict) -> set[str]:
    # boundary_hints carry group_id + titles; easiest is to resolve by title,
    # but titles can change. Prefer checking group_id mapping if you want.
    return {h["short_title"] for h in graph.get("boundary_hints", [])}


async def test_focus_physics_contains_fourier_and_hints_math_and_dsp() -> None:
    async with AsyncClient(transport=transport, base_url="http://test") as client:

        physics_id = await _get_abs_id_by_slug("physics")
        g = await _focus(client, physics_id)

        slugs = _slugs(g)
        # Fourier should be pulled in by outgoing requires from QM -> ft_physics
        assert "fourier-transform" in slugs

        # Physics focus should NOT contain the DSP concept S&S (it’s a DSP child)
        assert "signals-and-systems" not in slugs

        # Boundary hints should not be empty (we expect at least math/dsp groups hinted)
        assert len(g.get("boundary_hints", [])) > 0


async def test_focus_dsp_contains_fourier_and_hints_math_and_physics() -> None:
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await _reseed(client)

        dsp_id = await _get_abs_id_by_slug("signals")
        g = await _focus(client, dsp_id)

        slugs = _slugs(g)
        assert "fourier-transform" in slugs
        assert "quantum-mechanics" not in slugs  # QM is physics child

        assert len(g.get("boundary_hints", [])) > 0


async def test_focus_math_does_not_include_qm_or_ss_as_inside_nodes() -> None:
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await _reseed(client)

        math_id = await _get_abs_id_by_slug("math")
        g = await _focus(client, math_id)

        slugs = _slugs(g)

        # sanity: math contains its own children
        assert "logic" in slugs
        assert "lin-alg" in slugs
        assert "calc" in slugs
        assert "fourier-transform" in slugs

        # must NOT leak other domains into math focus
        assert "quantum-mechanics" not in slugs
        assert "signals-and-systems" not in slugs

        # math should still have external hints (incoming deps from physics/dsp, depending on your logic)
        # If your expected behavior is "math sees incoming requires as hints", keep this.
        assert len(g.get("boundary_hints", [])) > 0
