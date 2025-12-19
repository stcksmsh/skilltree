from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import AbstractNode, ImplNode, ImplContext, Edge, EdgeType
from ..schemas import GraphOut, AbstractNodeOut, ImplOut, EdgeOut, BoundaryHintOut

import logging

log = logging.getLogger("graph.focus")


# ----------------------------
# Public entry point
# ----------------------------

async def build_focus_graph(*, session: AsyncSession, focus_abstract_id: UUID) -> GraphOut:
    """
    Focus graph rules (current MVP, corrected):
    - Base inside abstracts = focus + direct children
    - Expand inside abstracts with OUTGOING external concept targets:
        - If an ACTIVE inside impl has an edge to an impl whose abstract is a concept outside the inside set,
          include that concept abstract (1-hop).
        - This is what makes DSP/Physics show Fourier even though Fourier's abstract lives under Math.
      IMPORTANT: this is OUTGOING only, so Math focus won't pull in QM/S&S.
    - Active impls in this focus context:
        - impl has NO ImplContext rows  => global => active everywhere
        - impl has ImplContext rows     => active iff focus_abstract_id is in them
      Active impls are used for INTERNAL edges + impl_nodes.
    - Boundary hints consider edges touching ANY impl that belongs to inside abstracts,
      INCLUDING inactive variants (so we can hint cross-domain prerequisites through inactive variants).
    """

    # ---------- 1) focus ----------
    focus = await session.get(AbstractNode, focus_abstract_id)
    if not focus:
        raise HTTPException(status_code=404, detail="Abstract node not found")

    # ---------- 2) inside abstracts = focus + direct children ----------
    children = (
        await session.execute(
            select(AbstractNode).where(AbstractNode.parent_id == focus_abstract_id)
        )
    ).scalars().all()

    inside_abs: list[AbstractNode] = [focus, *children]
    inside_abs_ids: set[UUID] = {n.id for n in inside_abs}

    # ---------- 3) build state for base inside ----------
    state = await _build_state(session=session, focus=focus, inside_abs_ids=inside_abs_ids)

    log.debug(
        "STATE1 focus=%s inside_abs=%s inside_impls_all=%s inside_impls_active=%s edges_any_inside=%s",
        str(focus.id),
        len(inside_abs_ids),
        len(state.inside_impls_all),
        len(state.inside_impls_active),
        len(state.touching_edges_any_inside_impl),
    )

    # ---------- 4) expand with OUTGOING external concept targets ----------
    extra_abs_ids = _collect_outgoing_concept_targets_to_include(
        inside_abs_ids=inside_abs_ids,
        inside_impl_ids_active=state.inside_impl_ids_active,
        touching_edges_any_inside_impl=state.touching_edges_any_inside_impl,
        impl_by_id=state.impl_by_id,
        abs_by_id=state.abs_by_id,
    )

    log.debug("EXPAND outgoing_concept_targets count=%s ids=%s",
              len(extra_abs_ids), sorted(map(str, extra_abs_ids))[:20])

    if extra_abs_ids:
        extra_abs = (
            await session.execute(select(AbstractNode).where(AbstractNode.id.in_(extra_abs_ids)))
        ).scalars().all()

        inside_abs.extend(extra_abs)
        inside_abs_ids |= extra_abs_ids

        # rebuild state because "inside abstracts" changed (adds Fourier into DSP/Physics focus)
        state = await _build_state(session=session, focus=focus, inside_abs_ids=inside_abs_ids)

        log.debug(
            "STATE2 focus=%s inside_abs=%s inside_impls_all=%s inside_impls_active=%s edges_any_inside=%s",
            str(focus.id),
            len(inside_abs_ids),
            len(state.inside_impls_all),
            len(state.inside_impls_active),
            len(state.touching_edges_any_inside_impl),
        )

    # ---------- 5) boundary grouping helpers ----------
    focus_ancestor_ids = _build_ancestor_set(focus, state.abs_by_id)

    def find_boundary_group(outside_abs: AbstractNode) -> AbstractNode:
        """
        "Topmost outside node before entering focus ancestor chain":
        Walk up outside_abs -> parent -> ... until next parent would be in focus_ancestor_ids, or root.
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
                return cur
            cur = nxt

    # ---------- 6) internal edges (ACTIVE-only) ----------
    internal_edges: list[Edge] = []
    for e in state.touching_edges_any_inside_impl:
        if e.src_impl_id in state.inside_impl_ids_active and e.dst_impl_id in state.inside_impl_ids_active:
            internal_edges.append(e)

    # ---------- 7) boundary hints (ANY inside-impl, including inactive variants) ----------
    boundary_map: dict[tuple[UUID, EdgeType], int] = {}

    for e in state.touching_edges_any_inside_impl:
        src_impl = state.impl_by_id.get(e.src_impl_id)
        dst_impl = state.impl_by_id.get(e.dst_impl_id)
        if not src_impl or not dst_impl:
            continue

        src_abs_id = src_impl.abstract_id
        dst_abs_id = dst_impl.abstract_id

        src_abs_in = src_abs_id in inside_abs_ids
        dst_abs_in = dst_abs_id in inside_abs_ids

        # boundary edge = exactly one abstract is inside
        if not (src_abs_in ^ dst_abs_in):
            continue

        outside_abs_id = dst_abs_id if src_abs_in else src_abs_id
        outside_abs = state.abs_by_id.get(outside_abs_id)
        if not outside_abs:
            continue

        boundary_group = find_boundary_group(outside_abs)
        key = (boundary_group.id, e.type)
        boundary_map[key] = boundary_map.get(key, 0) + 1

    log.debug("BOUNDARY internal_edges=%s boundary_map_keys=%s", len(internal_edges), len(boundary_map))

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

    # ---------- 8) pack output ----------
    # abstract.impls should include ALL impl variants for that abstract (variant picker),
    # even if some variants are inactive in this focus.
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
                    for i in sorted(impls, key=lambda x: x.variant_key)
                ],
            )
        )

    return GraphOut(
        abstract_nodes=abstract_nodes_out,
        # impl_nodes = ACTIVE impls only (prevents leaking variants into other contexts)
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
# Outgoing expansion helper
# ----------------------------

def _collect_outgoing_concept_targets_to_include(
    *,
    inside_abs_ids: set[UUID],
    inside_impl_ids_active: set[UUID],
    touching_edges_any_inside_impl: list[Edge],
    impl_by_id: dict[UUID, ImplNode],
    abs_by_id: dict[UUID, AbstractNode],
) -> set[UUID]:
    """
    Include external concept abstracts that are *targets* of edges from ACTIVE inside impls.

    This is the key asymmetry:
    - DSP focus: S&S (inside, active) -> Fourier(signals) (outside concept) => include Fourier.
    - Physics focus: QM (inside, active) -> Fourier(physics) (outside concept) => include Fourier.
    - Math focus: QM/S&S are not targets of edges from Math active impls => NOT included.
    """
    extra_abs_ids: set[UUID] = set()

    for e in touching_edges_any_inside_impl:
        if e.src_impl_id not in inside_impl_ids_active:
            continue  # ONLY outgoing from active inside

        dst_impl = impl_by_id.get(e.dst_impl_id)
        if not dst_impl:
            continue

        dst_abs_id = dst_impl.abstract_id
        if dst_abs_id in inside_abs_ids:
            continue

        dst_abs = abs_by_id.get(dst_abs_id)
        if dst_abs and dst_abs.kind == "concept":
            extra_abs_ids.add(dst_abs_id)

    return extra_abs_ids


# ----------------------------
# Internal state builder
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
    # 1) ALL impls for inside abstracts (variants included)
    inside_impls_all = (
        await session.execute(
            select(ImplNode).where(ImplNode.abstract_id.in_(inside_abs_ids))
        )
    ).scalars().all()
    inside_impl_ids_all = {i.id for i in inside_impls_all}

    # 2) contexts for those impls
    impl_ctx: dict[UUID, set[UUID]] = {}
    if inside_impl_ids_all:
        rows = (
            await session.execute(
                select(ImplContext).where(ImplContext.impl_id.in_(inside_impl_ids_all))
            )
        ).scalars().all()
        for c in rows:
            impl_ctx.setdefault(c.impl_id, set()).add(c.context_abstract_id)

    # Active rule: global if no ImplContext rows, otherwise must match focus id
    def impl_is_active_in_focus(impl_id: UUID) -> bool:
        ctxs = impl_ctx.get(impl_id)
        return (ctxs is None) or (focus.id in ctxs)

    inside_impls_active = [i for i in inside_impls_all if impl_is_active_in_focus(i.id)]
    inside_impl_ids_active = {i.id for i in inside_impls_active}

    # 3) edges touching ANY inside impl (for boundary)
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

    # 4) load impls referenced by those edges
    edge_impl_ids = {e.src_impl_id for e in touching_edges_any_inside_impl} | {e.dst_impl_id for e in touching_edges_any_inside_impl}

    edge_impls: list[ImplNode] = []
    if edge_impl_ids:
        edge_impls = (
            await session.execute(select(ImplNode).where(ImplNode.id.in_(edge_impl_ids)))
        ).scalars().all()

    impl_by_id: dict[UUID, ImplNode] = {i.id: i for i in edge_impls}

    # 5) load abstracts referenced by those impls (+ focus)
    abs_ids = {i.abstract_id for i in edge_impls} | {focus.id}
    abstracts = (
        await session.execute(select(AbstractNode).where(AbstractNode.id.in_(abs_ids)))
    ).scalars().all()
    abs_by_id: dict[UUID, AbstractNode] = {a.id: a for a in abstracts}

    await _preload_ancestors(session=session, abs_by_id=abs_by_id)

    log.debug(
        "BUILD_STATE inside_impls_all=%s inside_impls_active=%s edges_any_inside=%s edge_impls=%s abs_by_id=%s impl_ctx_keys=%s",
        len(inside_impls_all),
        len(inside_impls_active),
        len(touching_edges_any_inside_impl),
        len(edge_impls),
        len(abs_by_id),
        len(impl_ctx),
    )

    return _State(
        inside_impls_all=inside_impls_all,
        inside_impls_active=inside_impls_active,
        inside_impl_ids_active=inside_impl_ids_active,
        touching_edges_any_inside_impl=touching_edges_any_inside_impl,
        impl_by_id=impl_by_id,
        impl_ctx=impl_ctx,
        abs_by_id=abs_by_id,
    )


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
