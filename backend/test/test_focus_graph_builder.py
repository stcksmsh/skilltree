import pytest

from app.services.graph_focus import build_focus_graph
from test.helpers import slugs_builder, hint_pairs_builder, abs_id_by_slug

pytestmark = pytest.mark.asyncio

async def test_physics_focus_contains_fourier_and_has_expected_boundary_hints(session) -> None:
    physics_id = await abs_id_by_slug(session, "physics")
    g = await build_focus_graph(session=session, focus_abstract_id=physics_id)

    slugs = slugs_builder(g)
    assert "fourier-transform" in slugs
    assert "signals-and-systems" not in slugs

    pairs = hint_pairs_builder(g)
    assert ("Math", "recommended") in pairs
    assert ("DSP", "requires") in pairs