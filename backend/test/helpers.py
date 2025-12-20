from __future__ import annotations

from collections import Counter
from typing import Any, Mapping

from httpx import AsyncClient

from sqlalchemy import select
from app.models import AbstractNode


# -------------------------
# Shared API dict access
# -------------------------

def _api_nodes(g: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    nodes = g.get("abstract_nodes")
    if not isinstance(nodes, list):
        raise AssertionError(f"Expected g['abstract_nodes'] to be a list, got: {type(nodes)}")
    # ensure elements are dict-like
    for i, n in enumerate(nodes):
        if not isinstance(n, Mapping):
            raise AssertionError(f"Expected abstract_nodes[{i}] to be a mapping, got: {type(n)}")
    return nodes  # type: ignore[return-value]


def slugs_api(g: Mapping[str, Any]) -> set[str]:
    return {str(n.get("slug")) for n in _api_nodes(g) if n.get("slug") is not None}


def node_by_slug_api(g: Mapping[str, Any], slug: str) -> Mapping[str, Any] | None:
    for n in _api_nodes(g):
        if n.get("slug") == slug:
            return n
    return None


def fourier_variant_keys_api(g: Mapping[str, Any]) -> set[str]:
    n = node_by_slug_api(g, "fourier-transform")
    if not n:
        return set()
    impls = n.get("impls") or []
    if not isinstance(impls, list):
        raise AssertionError(f"Expected fourier.impls to be a list, got: {type(impls)}")
    return {i["variant_key"] for i in impls if isinstance(i, Mapping) and "variant_key" in i}


def impl_variant_keys_api(g: Mapping[str, Any]) -> dict[str, set[str]]:
    nodes = _api_nodes(g)
    by_abs_id = {n["id"]: n["slug"] for n in nodes if "id" in n and "slug" in n}

    impl_nodes = g.get("impl_nodes") or []
    if not isinstance(impl_nodes, list):
        raise AssertionError(f"Expected g['impl_nodes'] to be a list, got: {type(impl_nodes)}")

    out: dict[str, set[str]] = {}
    for impl in impl_nodes:
        if not isinstance(impl, Mapping):
            continue
        abs_id = impl.get("abstract_id")
        slug = by_abs_id.get(abs_id)
        if not slug:
            continue
        vk = impl.get("variant_key")
        if vk is None:
            continue
        out.setdefault(slug, set()).add(str(vk))
    return out


def edge_type_counts_api(g: Mapping[str, Any]) -> Counter[str]:
    edges = g.get("edges") or []
    if not isinstance(edges, list):
        raise AssertionError(f"Expected g['edges'] to be a list, got: {type(edges)}")
    return Counter(e.get("type") for e in edges if isinstance(e, Mapping) and e.get("type") is not None)


def hint_pairs_api(g: Mapping[str, Any]) -> set[tuple[str, str]]:
    hints = g.get("boundary_hints") or []
    if not isinstance(hints, list):
        raise AssertionError(f"Expected g['boundary_hints'] to be a list, got: {type(hints)}")
    return {
        (str(h["short_title"]), str(h["type"]))
        for h in hints
        if isinstance(h, Mapping) and "short_title" in h and "type" in h
    }


def hint_counts_api(g: Mapping[str, Any]) -> Counter[tuple[str, str]]:
    hints = g.get("boundary_hints") or []
    if not isinstance(hints, list):
        raise AssertionError(f"Expected g['boundary_hints'] to be a list, got: {type(hints)}")
    return Counter(
        (str(h["short_title"]), str(h["type"]))
        for h in hints
        if isinstance(h, Mapping) and "short_title" in h and "type" in h
    )


# -------------------------
# Builder (pydantic) access
# -------------------------

def slugs_builder(g: Any) -> set[str]:
    return {n.slug for n in g.abstract_nodes}


def hint_pairs_builder(g: Any) -> set[tuple[str, str]]:
    return {(h.short_title, h.type) for h in g.boundary_hints}


# -------------------------
# DB helper
# -------------------------

async def abs_id_by_slug(session, slug: str) -> str:
    row = (
        await session.execute(select(AbstractNode).where(AbstractNode.slug == slug))
    ).scalar_one()
    return str(row.id)

async def focus(client: AsyncClient, abstract_id: str) -> Any:
    r = await client.get(f"/api/graph/focus/{abstract_id}")
    assert r.status_code == 200, r.text
    return r.json()