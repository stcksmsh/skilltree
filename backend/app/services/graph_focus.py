# services/graph_focus.py
from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import AbstractNode, ImplNode, ImplContext, Edge, EdgeType
from ..schemas import GraphOut, AbstractNodeOut, ImplOut, EdgeOut, BoundaryHintOut

import logging

log = logging.getLogger("graph.focus")


async def build_focus_graph(*, session: AsyncSession, focus_abstract_id: UUID) -> GraphOut:
    """
    Focus graph:
    - focus_abstract_id must be a HUB (level-2 group)
    - visible abstracts = ALL descendants of that hub
    - focus node itself is NOT included

    Boundary hints are DIRECTIONAL relative to inside set:
      - depends_on: inside -> outside (external prerequisites)
      - used_by:   outside -> inside (external dependents)
    """

    focus = await session.get(AbstractNode, focus_abstract_id)
    if not focus:
        raise HTTPException(status_code=404, detail="Abstract node not found")

    inside_abs = await _load_descendants(session=session, root_id=focus_abstract_id)
    inside_abs_ids = {n.id for n in inside_abs}

    if not inside_abs_ids:
        return GraphOut(
            abstract_nodes=[],
            impl_nodes=[],
            edges=[],
            related_edges=[],
            boundary_hints=[],
        )

    state = await _build_state(session=session, focus=focus, inside_abs_ids=inside_abs_ids)

    focus_ancestor_ids = _build_ancestor_set(focus, state.abs_by_id)

    def find_boundary_group(outside_abs: AbstractNode) -> AbstractNode:
        """
        Walk up outside_abs until we'd enter the focus ancestor chain (or root).
        Returns the "boundary group" node to attach the chip to.
        """
        cur = outside_abs
        while True:
            pid = cur.parent_id
            if pid is None or pid in focus_ancestor_ids:
                return cur
            nxt = state.abs_by_id.get(pid)
            if nxt is None:
                return cur
            cur = nxt

    # INTERNAL edges: only ACTIVE impls, both endpoints inside
    internal_edges = [
        e for e in state.touching_edges_any_inside_impl
        if e.src_impl_id in state.inside_impl_ids_active
        and e.dst_impl_id in state.inside_impl_ids_active
    ]

    # BOUNDARY hints: edges touching ANY inside impl (including inactive variants),
    # but we expose direction to avoid incorrect "requires" narratives.
    boundary_map: dict[tuple[UUID, EdgeType, str], int] = {}

    for e in state.touching_edges_any_inside_impl:
        src = state.impl_by_id.get(e.src_impl_id)
        dst = state.impl_by_id.get(e.dst_impl_id)
        if not src or not dst:
            continue

        src_in = src.abstract_id in inside_abs_ids
        dst_in = dst.abstract_id in inside_abs_ids

        # boundary edge = exactly one endpoint abstract is inside
        if not (src_in ^ dst_in):
            continue

        # direction relative to inside:
        # - inside -> outside => inside depends_on outside
        # - outside -> inside => outside used_by inside
        if src_in and not dst_in:
            direction = "depends_on"
            outside_abs_id = dst.abstract_id
        else:
            direction = "used_by"
            outside_abs_id = src.abstract_id

        outside_abs = state.abs_by_id.get(outside_abs_id)
        if not outside_abs:
            continue

        g = find_boundary_group(outside_abs)
        key = (g.id, e.type, direction)
        boundary_map[key] = boundary_map.get(key, 0) + 1

    # deterministic ordering: depends_on first, requires before recommended, then count desc
    def _dir_order(d: str) -> int:
        return 0 if d == "depends_on" else 1

    def _type_order(t: EdgeType) -> int:
        return 0 if t == EdgeType.requires else 1

    boundary_items = sorted(
        boundary_map.items(),
        key=lambda kv: (
            _dir_order(kv[0][2]),
            _type_order(kv[0][1]),
            -kv[1],
            state.abs_by_id[kv[0][0]].title,
        ),
    )

    boundary_hints = [
        BoundaryHintOut(
            group_id=gid,
            title=state.abs_by_id[gid].title,
            short_title=state.abs_by_id[gid].short_title,
            type=edge_type.value,
            count=count,
            direction=direction,
        )
        for (gid, edge_type, direction), count in boundary_items
    ]

    # has_children within inside set (so nested groups remain drillable)
    children_counts = dict(
        (
            await session.execute(
                select(AbstractNode.parent_id, func.count())
                .where(AbstractNode.parent_id.in_(inside_abs_ids))
                .group_by(AbstractNode.parent_id)
            )
        ).all()
    )

    # include ALL impl variants in abstract.impls (variant picker),
    # but impl_nodes = ACTIVE impls only
    abs_id_to_impls_all: dict[UUID, list[ImplNode]] = {}
    for i in state.inside_impls_all:
        abs_id_to_impls_all.setdefault(i.abstract_id, []).append(i)

    def pick_default_impl_id(impls: list[ImplNode]) -> UUID | None:
        if not impls:
            return None
        core = next((x for x in impls if x.variant_key == "core"), None)
        return core.id if core else sorted(impls, key=lambda x: x.variant_key)[0].id

    abstract_nodes_out: list[AbstractNodeOut] = []
    for n in inside_abs:
        impls = abs_id_to_impls_all.get(n.id, [])
        abstract_nodes_out.append(
            AbstractNodeOut(
                id=n.id,
                slug=n.slug,
                title=n.title,
                short_title=n.short_title,
                summary=n.summary,
                body_md=n.body_md,
                kind=n.kind.value if hasattr(n.kind, "value") else str(n.kind),
                parent_id=n.parent_id,
                has_children=(children_counts.get(n.id, 0) > 0),
                has_variants=(len(impls) > 1),
                default_impl_id=pick_default_impl_id(impls),
                impls=[
                    ImplOut(
                        id=i.id,
                        abstract_id=i.abstract_id,
                        variant_key=i.variant_key,
                        contract_md=i.contract_md,
                    )
                    for i in sorted(impls, key=lambda x: x.variant_key)
                ],
            )
        )

    return GraphOut(
        abstract_nodes=abstract_nodes_out,
        impl_nodes=[
            ImplOut(
                id=i.id,
                abstract_id=i.abstract_id,
                variant_key=i.variant_key,
                contract_md=i.contract_md,
            )
            for i in state.inside_impls_active
        ],
        edges=[
            EdgeOut(
                id=e.id,
                src_impl_id=e.src_impl_id,
                dst_impl_id=e.dst_impl_id,
                type=e.type.value,
                rank=e.rank,
            )
            for e in internal_edges
        ],
        related_edges=[],
        boundary_hints=boundary_hints,
    )


# ----------------------------
# Internal state builder (unchanged)
# ----------------------------

@dataclass(frozen=True)
class _State:
    inside_impls_all: list[ImplNode]
    inside_impls_active: list[ImplNode]
    inside_impl_ids_active: set[UUID]
    touching_edges_any_inside_impl: list[Edge]

    impl_by_id: dict[UUID, ImplNode]
    impl_ctx: dict[UUID, set[UUID]]
    abs_by_id: dict[UUID, AbstractNode]


async def _build_state(*, session: AsyncSession, focus: AbstractNode, inside_abs_ids: set[UUID]) -> _State:
    inside_impls_all = (
        await session.execute(
            select(ImplNode).where(ImplNode.abstract_id.in_(inside_abs_ids))
        )
    ).scalars().all()
    inside_impl_ids_all = {i.id for i in inside_impls_all}

    impl_ctx: dict[UUID, set[UUID]] = {}
    if inside_impl_ids_all:
        rows = (
            await session.execute(
                select(ImplContext).where(ImplContext.impl_id.in_(inside_impl_ids_all))
            )
        ).scalars().all()
        for c in rows:
            impl_ctx.setdefault(c.impl_id, set()).add(c.context_abstract_id)

    def impl_is_active_in_focus(impl_id: UUID) -> bool:
        ctxs = impl_ctx.get(impl_id)
        return (ctxs is None) or (focus.id in ctxs)

    inside_impls_active = [i for i in inside_impls_all if impl_is_active_in_focus(i.id)]
    inside_impl_ids_active = {i.id for i in inside_impls_active}

    touching_edges_any_inside_impl: list[Edge] = []
    if inside_impl_ids_all:
        touching_edges_any_inside_impl = (
            await session.execute(
                select(Edge).where(
                    (Edge.src_impl_id.in_(inside_impl_ids_all)) |
                    (Edge.dst_impl_id.in_(inside_impl_ids_all))
                )
            )
        ).scalars().all()

    edge_impl_ids = {e.src_impl_id for e in touching_edges_any_inside_impl} | {
        e.dst_impl_id for e in touching_edges_any_inside_impl
    }

    edge_impls: list[ImplNode] = []
    if edge_impl_ids:
        edge_impls = (
            await session.execute(select(ImplNode).where(ImplNode.id.in_(edge_impl_ids)))
        ).scalars().all()

    impl_by_id: dict[UUID, ImplNode] = {i.id: i for i in edge_impls}

    abs_ids = {i.abstract_id for i in edge_impls} | {focus.id}
    abstracts = (
        await session.execute(select(AbstractNode).where(AbstractNode.id.in_(abs_ids)))
    ).scalars().all()
    abs_by_id: dict[UUID, AbstractNode] = {a.id: a for a in abstracts}

    await _preload_ancestors(session=session, abs_by_id=abs_by_id)

    return _State(
        inside_impls_all=inside_impls_all,
        inside_impls_active=inside_impls_active,
        inside_impl_ids_active=inside_impl_ids_active,
        touching_edges_any_inside_impl=touching_edges_any_inside_impl,
        impl_by_id=impl_by_id,
        impl_ctx=impl_ctx,
        abs_by_id=abs_by_id,
    )


def _build_ancestor_set(focus: AbstractNode, abs_by_id: dict[UUID, AbstractNode]) -> set[UUID]:
    ids: set[UUID] = set()
    cur = focus
    while True:
        ids.add(cur.id)
        if cur.parent_id is None:
            break
        nxt = abs_by_id.get(cur.parent_id)
        if nxt is None:
            break
        cur = nxt
    return ids


async def _preload_ancestors(*, session: AsyncSession, abs_by_id: dict[UUID, AbstractNode]) -> None:
    missing: set[UUID] = set()

    for a in list(abs_by_id.values()):
        pid = a.parent_id
        if pid is not None and pid not in abs_by_id:
            missing.add(pid)

    while missing:
        rows = (
            await session.execute(select(AbstractNode).where(AbstractNode.id.in_(missing)))
        ).scalars().all()

        missing.clear()
        for p in rows:
            abs_by_id[p.id] = p
            if p.parent_id is not None and p.parent_id not in abs_by_id:
                missing.add(p.parent_id)


async def _load_descendants(*, session: AsyncSession, root_id: UUID) -> list[AbstractNode]:
    out: list[AbstractNode] = []
    frontier: list[UUID] = [root_id]
    seen: set[UUID] = {root_id}

    while frontier:
        rows = (
            await session.execute(
                select(AbstractNode).where(AbstractNode.parent_id.in_(frontier))
            )
        ).scalars().all()

        if not rows:
            break

        out.extend(rows)

        nxt: list[UUID] = []
        for n in rows:
            if n.id not in seen:
                seen.add(n.id)
                nxt.append(n.id)
        frontier = nxt

    return out
