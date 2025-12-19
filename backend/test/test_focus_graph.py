import pytest
import httpx
from httpx import AsyncClient

from app.main import app
from helpers import slugs_api, hint_pairs_api, hint_counts_api, abs_id_by_slug, focus

pytestmark = pytest.mark.asyncio
transport = httpx.ASGITransport(app=app)

async def test_focus_physics_contains_fourier_and_hints_math_and_dsp(session) -> None:
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        physics_id = await abs_id_by_slug(session, "physics")
        g = await focus(client, physics_id)

        slugs = slugs_api(g)
        assert "fourier-transform" in slugs
        assert "signals-and-systems" not in slugs  # don't leak DSP child into physics focus

        pairs = hint_pairs_api(g)
        # Physics should hint to DSP as required and Math as recommended
        assert ("Math", "recommended") in pairs
        assert ("DSP", "requires") in pairs

        count = hint_counts_api(g)
        assert all(v > 0 for v in count.values())

async def test_focus_dsp_contains_fourier_and_hints_math_and_physics(session) -> None:
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        dsp_id = await abs_id_by_slug(session, "signals")
        g = await focus(client, dsp_id)

        slugs = slugs_api(g)
        assert "fourier-transform" in slugs
        assert "quantum-mechanics" not in slugs  # don't leak physics child into DSP focus

        pairs = hint_pairs_api(g)
        assert ("Math", "recommended") in pairs
        assert ("Phys", "requires") in pairs

        count = hint_counts_api(g)
        assert all(v > 0 for v in count.values())


async def test_focus_math_does_not_include_qm_or_ss_as_nodes_but_hints_external_requires(session) -> None:
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        math_id = await abs_id_by_slug(session, "math")
        g = await focus(client, math_id)

        slugs = slugs_api(g)
        assert {"logic", "lin-alg", "calc", "fourier-transform"} <= slugs

        assert "quantum-mechanics" not in slugs
        assert "signals-and-systems" not in slugs

        pairs = hint_pairs_api(g)
        # math should see incoming requires from Phys & DSP as boundary hints
        assert ("Phys", "requires") in pairs
        assert ("DSP", "requires") in pairs
