from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import (
    AbstractNode,
    AbstractMembership,
    ImplNode,
    ImplContext,
    Edge,
    EdgeType,
)
from ..schemas import (
    GraphOut,
    AbstractNodeOut,
    ImplOut,
    EdgeOut,
    BoundaryHintOut,
)


async def build_focus_graph(*, session: AsyncSession, focus_abstract_id: UUID) -> GraphOut:
    """
    Focus graph (hub drill-down):

    - focus_abstract_id is a hub/group
    - inside abstracts =
        * ALL descendants of the focus hub
        * PLUS all abstracts explicitly belonging to the hub via AbstractMembership
    - focus node itself is NOT included
    - internal edges use ACTIVE impls only
    - boundary hints are DIRECTIONAL:
        * depends_on : inside -> outside
        * used_by    : outside -> inside
    - boundary grouping is HUB-AWARE (membership first, taxonomy fallback)
    """

    # ---------- load focus ----------
    focus = await session.get(AbstractNode, focus_abstract_id)
    if not focus:
        raise HTTPException(status_code=404, detail="Abstract node not found")

    # ---------- inside abstracts (descendants) ----------
    inside_abs = await _load_descendants(session=session, root_id=focus_abstract_id)

    # ---------- inside abstracts (memberships) ----------
    mem_rows = (
        await session.execute(
            select(AbstractMembership)
            .where(AbstractMembership.hub_id == focus_abstract_id)
        )
    ).scalars().all()

    mem_abs_ids = {m.abstract_id for m in mem_rows}
    if mem_abs_ids:
        mem_abs = (
            await session.execute(
                select(AbstractNode).where(AbstractNode.id.in_(mem_abs_ids))
            )
        ).scalars().all()

        seen = {n.id for n in inside_abs}
        for n in mem_abs:
            if n.id != focus_abstract_id and n.id not in seen:
                inside_abs.append(n)
                seen.add(n.id)

    inside_abs_ids = {n.id for n in inside_abs}

    if not inside_abs_ids:
        return GraphOut(
            abstract_nodes=[],
            impl_nodes=[],
            edges=[],
            related_edges=[],
            boundary_hints=[],
        )

    # ---------- build state ----------
    state = await _build_state(
        session=session,
        focus=focus,
        inside_abs_ids=inside_abs_ids,
    )

    # ---------- preload ALL memberships for boundary grouping ----------
    abs_ids_for_membership = set(state.abs_by_id.keys())
    mem_all = (
        await session.execute(
            select(AbstractMembership)
            .where(AbstractMembership.abstract_id.in_(abs_ids_for_membership))
        )
    ).scalars().all()

    hubs_by_abs: dict[UUID, set[UUID]] = {}
    for m in mem_all:
        hubs_by_abs.setdefault(m.abstract_id, set()).add(m.hub_id)

    # ensure hub abstracts themselves are loaded
    hub_ids = {m.hub_id for m in mem_all}
    missing_hubs = hub_ids - set(state.abs_by_id.keys())
    if missing_hubs:
        hubs = (
            await session.execute(
                select(AbstractNode).where(AbstractNode.id.in_(missing_hubs))
            )
        ).scalars().all()
        for h in hubs:
            state.abs_by_id[h.id] = h

    def _kind_str(a: AbstractNode) -> str:
        k = getattr(a, "kind", None)
        return k.value if hasattr(k, "value") else str(k)

    def _domain_root_id(abs_id: UUID) -> UUID | None:
        """
        Walk up taxonomy to the root. If the root is a group, treat it as a 'domain root'.
        """
        cur = state.abs_by_id.get(abs_id)
        if not cur:
            return None
        while cur.parent_id is not None:
            nxt = state.abs_by_id.get(cur.parent_id)
            if nxt is None:
                break
            cur = nxt
        return cur.id if _kind_str(cur) == "group" else None

    def _depth2_under_domain(abs_id: UUID, domain_id: UUID) -> UUID:
        """
        Return the 'domain-top item': the node whose parent is the domain root.
        If abs_id itself is already such a node, return it.
        If abs_id is the domain root, return it (fallback).
        """
        cur = state.abs_by_id.get(abs_id)
        if not cur:
            return abs_id

        # If the node is the domain itself
        if cur.id == domain_id:
            return cur.id

        while True:
            pid = cur.parent_id
            if pid is None:
                return cur.id
            if pid == domain_id:
                return cur.id
            nxt = state.abs_by_id.get(pid)
            if nxt is None:
                return cur.id
            cur = nxt

    def boundary_group_for(abs_id: UUID) -> UUID | None:
        """
        Group boundary hints by "domain-top item" (depth-2 under a domain),
        NOT by the domain root itself.

        Priority:
        1) Use taxonomy domain root of the outside node => return its depth-2 representative.
        2) If taxonomy doesn't yield a domain, try membership hub(s) => use hub as a domain root and return depth-2 rep if possible.
        3) Fallback: if nothing works, group by the outside node itself.
        """
        # 1) taxonomy-first: where does this node live?
        dom = _domain_root_id(abs_id)
        if dom is not None:
            return _depth2_under_domain(abs_id, dom)

        # 2) membership fallback: pick a hub and try to use it like a domain root
        hubs = hubs_by_abs.get(abs_id)
        if hubs:
            # don't group under the focus hub itself
            candidates = [h for h in hubs if h != focus_abstract_id]
            if candidates:
                hub_id = sorted(candidates, key=lambda x: str(x))[0]
                # if hub looks like a domain root, try to map abs_id to a depth-2 node
                hub_node = state.abs_by_id.get(hub_id)
                if hub_node is not None and hub_node.parent_id is None and _kind_str(hub_node) == "group":
                    return _depth2_under_domain(abs_id, hub_id)
                # otherwise, group to the hub directly (still better than "Physics" leaking everywhere)
                return hub_id

        # 3) fallback: group by the node itself
        return abs_id


    # ---------- internal edges (ACTIVE only) ----------
    internal_edges = [
        e for e in state.touching_edges_any_inside_impl
        if e.src_impl_id in state.inside_impl_ids_active
        and e.dst_impl_id in state.inside_impl_ids_active
    ]

    # ---------- directional boundary hints ----------
    boundary_map: dict[tuple[UUID, EdgeType, str], int] = {}

    for e in state.touching_edges_any_inside_impl:
        src = state.impl_by_id.get(e.src_impl_id)
        dst = state.impl_by_id.get(e.dst_impl_id)
        if not src or not dst:
            continue

        src_in = src.abstract_id in inside_abs_ids
        dst_in = dst.abstract_id in inside_abs_ids
        if not (src_in ^ dst_in):
            continue

        direction = "depends_on" if src_in and not dst_in else "used_by"
        outside_abs_id = dst.abstract_id if src_in else src.abstract_id

        gid = boundary_group_for(outside_abs_id)
        if gid is None or gid not in state.abs_by_id:
            continue

        boundary_map[(gid, e.type, direction)] = (
            boundary_map.get((gid, e.type, direction), 0) + 1
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
        for (gid, edge_type, direction), count in boundary_map.items()
    ]

    # ---------- children counts ----------
    children_counts = dict(
        (
            await session.execute(
                select(AbstractNode.parent_id, func.count())
                .where(AbstractNode.parent_id.in_(inside_abs_ids))
                .group_by(AbstractNode.parent_id)
            )
        ).all()
    )

    # ---------- impl grouping ----------
    abs_id_to_impls_all: dict[UUID, list[ImplNode]] = {}
    for i in state.inside_impls_all:
        abs_id_to_impls_all.setdefault(i.abstract_id, []).append(i)

    def pick_default_impl_id(impls: list[ImplNode]) -> UUID | None:
        if not impls:
            return None
        core = next((x for x in impls if x.variant_key == "core"), None)
        return core.id if core else sorted(impls, key=lambda x: x.variant_key)[0].id

    # ---------- pack abstracts ----------
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


# ============================================================================
# Internal helpers (unchanged)
# ============================================================================

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

    edge_impl_ids = (
        {e.src_impl_id for e in touching_edges_any_inside_impl}
        | {e.dst_impl_id for e in touching_edges_any_inside_impl}
    )

    edge_impls: list[ImplNode] = []
    if edge_impl_ids:
        edge_impls = (
            await session.execute(
                select(ImplNode).where(ImplNode.id.in_(edge_impl_ids))
            )
        ).scalars().all()

    impl_by_id: dict[UUID, ImplNode] = {i.id: i for i in edge_impls}

    abs_ids = {i.abstract_id for i in edge_impls} | {focus.id}
    abstracts = (
        await session.execute(
            select(AbstractNode).where(AbstractNode.id.in_(abs_ids))
        )
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


async def _preload_ancestors(*, session: AsyncSession, abs_by_id: dict[UUID, AbstractNode]) -> None:
    missing: set[UUID] = set()

    for a in list(abs_by_id.values()):
        pid = a.parent_id
        if pid is not None and pid not in abs_by_id:
            missing.add(pid)

    while missing:
        rows = (
            await session.execute(
                select(AbstractNode).where(AbstractNode.id.in_(missing))
            )
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
