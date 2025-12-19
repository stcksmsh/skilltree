from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import AbstractNode, ImplNode, ImplContext, Edge, EdgeType
from ..schemas import GraphOut, AbstractNodeOut, ImplOut, EdgeOut, BoundaryHintOut


# ----------------------------
# Public entry point
# ----------------------------

async def build_focus_graph(*, session: AsyncSession, focus_abstract_id: UUID) -> GraphOut:
    """
    Focus graph rules (current MVP):
    - "Inside" abstracts = focus + its direct children
    - Only include impls that are valid in this focus context:
        - impl has NO ImplContext rows  => global => included everywhere
        - impl has ImplContext rows     => included only if focus_abstract_id is in them
    - Pull in prerequisite *concept* abstracts (1-hop) if their impl is required by an inside impl
      AND that required impl is valid in this focus context.
    - Internal edges = edges whose endpoints are inside impl set after filtering.
    - Boundary hints = count edges crossing inside<->outside, grouped by "topmost outside group
      before entering focus's ancestor chain".
    """

    # ---------- 1) focus ----------
    focus = await session.get(AbstractNode, focus_abstract_id)
    if not focus:
        raise HTTPException(status_code=404, detail="Abstract node not found")

    # ---------- 2) inside abstracts = focus + direct children ----------
    children = (
        await session.execute(select(AbstractNode).where(AbstractNode.parent_id == focus_abstract_id))
    ).scalars().all()

    inside_abs: list[AbstractNode] = [focus, *children]
    inside_abs_ids: set[UUID] = {n.id for n in inside_abs}

    # We'll build state twice: once for initial inside, once after adding prereq concepts
    state = await _build_state(
        session=session,
        focus=focus,
        inside_abs_ids=inside_abs_ids,
    )

    # ---------- 3) include prerequisite concepts (1-hop) ----------
    extra_abs_ids = _collect_connected_concepts_to_include(
        focus_id=focus_abstract_id,
        inside_abs_ids=inside_abs_ids,
        inside_impl_ids=state.inside_impl_ids,
        touching_edges=state.touching_edges,
        impl_by_id=state.impl_by_id,
        impl_ctx=state.impl_ctx,
        abs_by_id=state.abs_by_id,
    )

    if extra_abs_ids:
        extra_abs = (
            await session.execute(select(AbstractNode).where(AbstractNode.id.in_(extra_abs_ids)))
        ).scalars().all()
        inside_abs.extend(extra_abs)
        inside_abs_ids |= extra_abs_ids

        # rebuild with expanded inside set (important!)
        state = await _build_state(
            session=session,
            focus=focus,
            inside_abs_ids=inside_abs_ids,
        )

    # ---------- 4) compute focus ancestor chain (for boundary grouping) ----------
    focus_ancestor_ids = _build_ancestor_set(focus, state.abs_by_id)

    def find_boundary_group(outside_abs: AbstractNode) -> AbstractNode:
        """
        "Topmost outside node before entering focus ancestor chain":
        Walk up outside_abs -> parent -> ... until next parent would be inside focus_ancestor_ids,
        or root.
        """
        cur = outside_abs
        while True:
            pid = cur.parent_id
            if pid is None:
                return cur
            if pid in focus_ancestor_ids:
                return cur
            nxt = state.abs_by_id.get(pid)
            if nxt is None:
                # should not happen if preload worked, but stay safe
                return cur
            cur = nxt

    # ---------- 5) internal edges + boundary hints ----------
    internal_edges: list[Edge] = []
    boundary_map: dict[tuple[UUID, EdgeType], int] = {}

    for e in state.touching_edges:
        # if an impl wasn't loaded for some reason, skip safely
        sa_impl = state.impl_by_id.get(e.src_impl_id)
        da_impl = state.impl_by_id.get(e.dst_impl_id)
        if not sa_impl or not da_impl:
            continue

        sa_abs = sa_impl.abstract_id
        da_abs = da_impl.abstract_id

        sa_in = e.src_impl_id in state.inside_impl_ids
        da_in = e.dst_impl_id in state.inside_impl_ids

        # internal = both endpoints inside impl set
        if sa_in and da_in:
            internal_edges.append(e)
            continue

        # boundary = exactly one endpoint inside
        if sa_in ^ da_in:
            outside_abs_id = da_abs if sa_in else sa_abs

            if outside_abs_id in inside_abs_ids:
                continue

            outside_abs = state.abs_by_id.get(outside_abs_id)
            if not outside_abs:
                continue
            boundary_group = find_boundary_group(outside_abs)
            key = (boundary_group.id, e.type)
            boundary_map[key] = boundary_map.get(key, 0) + 1

    boundary_hints = [
        BoundaryHintOut(
            group_id=gid,
            title=state.abs_by_id[gid].title,
            short_title=state.abs_by_id[gid].short_title,
            type=edge_type.value,
            count=count,
        )
        for (gid, edge_type), count in boundary_map.items()
    ]

    # ---------- 6) pack output ----------
    abs_id_to_impls: dict[UUID, list[ImplNode]] = {}
    for i in state.inside_impls:
        abs_id_to_impls.setdefault(i.abstract_id, []).append(i)

    def pick_default_impl_id(impls: list[ImplNode]) -> UUID | None:
        if not impls:
            return None
        core = next((x for x in impls if x.variant_key == "core"), None)
        return core.id if core else sorted(impls, key=lambda x: x.variant_key)[0].id

    abstract_nodes_out: list[AbstractNodeOut] = []
    for n in inside_abs:
        impls = abs_id_to_impls.get(n.id, [])
        abstract_nodes_out.append(
            AbstractNodeOut(
                id=n.id,
                slug=n.slug,
                title=n.title,
                short_title=n.short_title,
                summary=n.summary,
                body_md=n.body_md,
                kind=n.kind,
                parent_id=n.parent_id,
                has_children=(n.id == focus_abstract_id and len(children) > 0),
                has_variants=(len(impls) > 1),
                default_impl_id=pick_default_impl_id(impls),
                impls=[
                    ImplOut(
                        id=i.id,
                        abstract_id=i.abstract_id,
                        variant_key=i.variant_key,
                        contract_md=i.contract_md,
                    )
                    for i in impls
                ],
            )
        )

    return GraphOut(
        abstract_nodes=abstract_nodes_out,
        impl_nodes=[
            ImplOut(id=i.id, abstract_id=i.abstract_id, variant_key=i.variant_key, contract_md=i.contract_md)
            for i in state.inside_impls
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
# Internal state builder
# ----------------------------

@dataclass(frozen=True)
class _State:
    inside_impls: list[ImplNode]
    inside_impl_ids: set[UUID]
    touching_edges: list[Edge]
    impl_by_id: dict[UUID, ImplNode]
    impl_ctx: dict[UUID, set[UUID]]
    abs_by_id: dict[UUID, AbstractNode]


async def _build_state(*, session: AsyncSession, focus: AbstractNode, inside_abs_ids: set[UUID]) -> _State:
    """
    Build all the info needed to compute internal edges + boundary hints.
    Key: filters inside impls by ImplContext (prevents Fourier variants from leaking into other foci).
    """

    # 1) load all impls for inside abstracts
    all_inside_impls = (
        await session.execute(select(ImplNode).where(ImplNode.abstract_id.in_(inside_abs_ids)))
    ).scalars().all()
    all_inside_impl_ids = {i.id for i in all_inside_impls}

    # 2) load contexts for those impls (to filter)
    inside_ctx_rows = []
    if all_inside_impl_ids:
        inside_ctx_rows = (
            await session.execute(select(ImplContext).where(ImplContext.impl_id.in_(all_inside_impl_ids)))
        ).scalars().all()

    impl_ctx: dict[UUID, set[UUID]] = {}
    for c in inside_ctx_rows:
        impl_ctx.setdefault(c.impl_id, set()).add(c.context_abstract_id)

    def impl_is_active_in_focus(impl_id: UUID) -> bool:
        ctxs = impl_ctx.get(impl_id)
        return ctxs is None or focus.id in ctxs

    # 3) filter inside impls to active-in-focus
    inside_impls = [i for i in all_inside_impls if impl_is_active_in_focus(i.id)]
    inside_impl_ids = {i.id for i in inside_impls}

    # 4) touching edges (any edge that touches an active inside impl)
    touching_edges: list[Edge] = []
    if inside_impl_ids:
        touching_edges = (
            await session.execute(
                select(Edge).where(
                    (Edge.src_impl_id.in_(inside_impl_ids)) |
                    (Edge.dst_impl_id.in_(inside_impl_ids))
                )
            )
        ).scalars().all()

    # 5) load all impls referenced by these edges (for abs mapping + boundary)
    edge_impl_ids = {e.src_impl_id for e in touching_edges} | {e.dst_impl_id for e in touching_edges}

    edge_impls: list[ImplNode] = []
    if edge_impl_ids:
        edge_impls = (
            await session.execute(select(ImplNode).where(ImplNode.id.in_(edge_impl_ids)))
        ).scalars().all()

    impl_by_id: dict[UUID, ImplNode] = {i.id: i for i in edge_impls}

    # 6) load abstracts referenced by those impls
    abs_ids = {i.abstract_id for i in edge_impls}
    abstracts: list[AbstractNode] = []
    if abs_ids:
        abstracts = (
            await session.execute(select(AbstractNode).where(AbstractNode.id.in_(abs_ids)))
        ).scalars().all()

    abs_by_id: dict[UUID, AbstractNode] = {a.id: a for a in abstracts}

    # 7) ensure focus + ancestors are present (for boundary grouping)
    if focus.id not in abs_by_id:
        abs_by_id[focus.id] = focus

    await _preload_ancestors(session=session, abs_by_id=abs_by_id)

    # 8) ALSO ensure parents exist for any referenced abstracts (already handled by preload)
    return _State(
        inside_impls=inside_impls,
        inside_impl_ids=inside_impl_ids,
        touching_edges=touching_edges,
        impl_by_id=impl_by_id,
        impl_ctx=impl_ctx,
        abs_by_id=abs_by_id,
    )


def _collect_connected_concepts_to_include(
    *,
    focus_id: UUID,
    inside_abs_ids: set[UUID],
    inside_impl_ids: set[UUID],
    touching_edges: list[Edge],
    impl_by_id: dict[UUID, ImplNode],
    impl_ctx: dict[UUID, set[UUID]],
    abs_by_id: dict[UUID, AbstractNode],
) -> set[UUID]:
    extra_abs_ids: set[UUID] = set()

    def impl_active(impl_id: UUID) -> bool:
        ctxs = impl_ctx.get(impl_id)
        return ctxs is None or focus_id in ctxs

    for e in touching_edges:
        src_in = e.src_impl_id in inside_impl_ids
        dst_in = e.dst_impl_id in inside_impl_ids
        if not (src_in ^ dst_in):
            continue  # both in or both out -> not a 1-hop boundary neighbor

        outside_impl_id = e.dst_impl_id if src_in else e.src_impl_id
        if not impl_active(outside_impl_id):
            continue

        outside_impl = impl_by_id.get(outside_impl_id)
        if not outside_impl:
            continue

        outside_abs_id = outside_impl.abstract_id
        if outside_abs_id in inside_abs_ids:
            continue

        cand = abs_by_id.get(outside_abs_id)
        if cand and cand.kind == "concept":
            extra_abs_ids.add(outside_abs_id)

    return extra_abs_ids



# ----------------------------
# Ancestor helpers
# ----------------------------

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
    """
    Ensure all parents up to roots for currently-known nodes exist in abs_by_id.
    """
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
