# services/graph.py
from __future__ import annotations

import uuid as _uuid
from uuid import UUID
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..models import AbstractNode, ImplNode, Edge, RelatedEdge
from ..schemas import GraphOut, AbstractNodeOut, ImplOut, EdgeOut, RelatedEdgeOut


async def build_graph(session: AsyncSession) -> GraphOut:
    """
    Collapsed baseline graph:
    - Visible abstracts: top-level (parent_id is NULL)
    - Hidden abstracts: all non-top-level
    - Representative (rep) of any abstract = its top-level ancestor
    - To keep GraphOut shape stable:
      - impl_nodes includes EXACTLY ONE "representative impl" per visible abstract (default_impl_id)
      - edges are rewritten to connect representative impls of representative abstracts
      - related edges are rewritten to connect representative abstracts
    """

    # counts for has_children (for ALL abstracts, used when packing visible ones)
    children_cte = (
        select(AbstractNode.parent_id.label("id"), func.count().label("child_count"))
        .where(AbstractNode.parent_id.isnot(None))
        .group_by(AbstractNode.parent_id)
        .cte("children_cte")
    )

    # counts for has_variants (for ALL abstracts)
    variants_cte = (
        select(ImplNode.abstract_id.label("id"), func.count().label("impl_count"))
        .group_by(ImplNode.abstract_id)
        .cte("variants_cte")
    )

    q_abs = (
        select(
            AbstractNode,
            func.coalesce(children_cte.c.child_count, 0).label("child_count"),
            func.coalesce(variants_cte.c.impl_count, 0).label("impl_count"),
        )
        .outerjoin(children_cte, children_cte.c.id == AbstractNode.id)
        .outerjoin(variants_cte, variants_cte.c.id == AbstractNode.id)
        .options(selectinload(AbstractNode.impls))  # load impl list per abstract
    )

    abs_rows = (await session.execute(q_abs)).all()

    # Load all impls/edges/related (we rewrite down to baseline reps)
    impls_all = (await session.execute(select(ImplNode))).scalars().all()
    edges_all = (await session.execute(select(Edge))).scalars().all()
    related_all = (await session.execute(select(RelatedEdge))).scalars().all()

    # Index abstracts + counts
    abs_by_id: dict[UUID, AbstractNode] = {}
    child_count_by_id: dict[UUID, int] = {}
    impl_count_by_id: dict[UUID, int] = {}

    for a, child_count, impl_count in abs_rows:
        abs_by_id[a.id] = a
        child_count_by_id[a.id] = int(child_count or 0)
        impl_count_by_id[a.id] = int(impl_count or 0)

    # Visible = top-level only
    visible_abs_ids: set[UUID] = {a.id for a in abs_by_id.values() if a.parent_id is None}

    # Rep = top-level ancestor (cached)
    rep_cache: dict[UUID, UUID] = {}

    def rep(abs_id: UUID) -> UUID:
        if abs_id in rep_cache:
            return rep_cache[abs_id]
        cur = abs_by_id.get(abs_id)
        while cur is not None and cur.parent_id is not None:
            nxt = abs_by_id.get(cur.parent_id)
            if nxt is None:
                break
            cur = nxt
        rep_cache[abs_id] = cur.id if cur is not None else abs_id
        return rep_cache[abs_id]

    # Default impl picking
    def pick_default_impl_id(impl_list: list[ImplNode]) -> UUID | None:
        if not impl_list:
            return None
        core = next((x for x in impl_list if x.variant_key == "core"), None)
        if core:
            return core.id
        return sorted(impl_list, key=lambda x: x.variant_key)[0].id

    # Group ALL impls by abstract_id (authoritative)
    impls_by_abs: dict[UUID, list[ImplNode]] = {}
    for i in impls_all:
        impls_by_abs.setdefault(i.abstract_id, []).append(i)

    # Map visible abstract -> representative impl (default)

    _VIRTUAL_NS = _uuid.UUID("00000000-0000-0000-0000-000000000001")

    def virtual_impl_id(abs_id: UUID) -> UUID:
        # deterministic per abstract id
        return _uuid.uuid5(_VIRTUAL_NS, f"virtual-impl:{abs_id}")

    rep_impl_by_visible_abs: dict[UUID, UUID] = {}
    virtual_impls_out: list[ImplOut] = []

    for abs_id in visible_abs_ids:
        impl_list = impls_by_abs.get(abs_id, [])
        did = pick_default_impl_id(impl_list)
        if did is not None:
            rep_impl_by_visible_abs[abs_id] = did
        else:
            vid = virtual_impl_id(abs_id)
            rep_impl_by_visible_abs[abs_id] = vid
            # emit virtual impl node in payload so UI can map impl->abstract
            virtual_impls_out.append(
                ImplOut(
                    id=vid,
                    abstract_id=abs_id,
                    variant_key="__virtual__",
                    contract_md=None,
                )
            )



    # Build impl_by_id for edge rewrite
    impl_by_id: dict[UUID, ImplNode] = {i.id: i for i in impls_all}

    # --- rewrite edges to representative impl endpoints
    rewritten_edges: list[EdgeOut] = []
    for e in edges_all:
        src_impl = impl_by_id.get(e.src_impl_id)
        dst_impl = impl_by_id.get(e.dst_impl_id)
        if not src_impl or not dst_impl:
            continue

        src_abs_rep = rep(src_impl.abstract_id)
        dst_abs_rep = rep(dst_impl.abstract_id)

        if src_abs_rep == dst_abs_rep:
            continue

        src_rep_impl = rep_impl_by_visible_abs.get(src_abs_rep)
        dst_rep_impl = rep_impl_by_visible_abs.get(dst_abs_rep)
        if src_rep_impl is None or dst_rep_impl is None:
            continue

        rewritten_edges.append(
            EdgeOut(
                id=e.id,
                src_impl_id=src_rep_impl,
                dst_impl_id=dst_rep_impl,
                type=e.type.value if hasattr(e.type, "value") else str(e.type),
                rank=e.rank,
            )
        )

    # --- rewrite related edges to representative abstract endpoints
    rewritten_related: list[RelatedEdgeOut] = []
    for r in related_all:
        a_rep = rep(r.a_id)
        b_rep = rep(r.b_id)
        if a_rep == b_rep:
            continue
        # keep canonical order as best effort
        a_id, b_id = (a_rep, b_rep) if str(a_rep) < str(b_rep) else (b_rep, a_rep)
        rewritten_related.append(RelatedEdgeOut(a_id=a_id, b_id=b_id))

    # --- pack visible abstract nodes only (top-level)
    abs_out: list[AbstractNodeOut] = []
    for abs_id in sorted(visible_abs_ids, key=lambda x: str(x)):
        a = abs_by_id[abs_id]
        impl_list = impls_by_abs.get(a.id, [])

        abs_out.append(
            AbstractNodeOut(
                id=a.id,
                slug=a.slug,
                title=a.title,
                short_title=a.short_title,
                summary=a.summary,
                body_md=a.body_md,
                kind=a.kind.value if hasattr(a.kind, "value") else str(a.kind),
                parent_id=a.parent_id,
                has_children=(child_count_by_id.get(a.id, 0) > 0),
                has_variants=(impl_count_by_id.get(a.id, 0) > 1),
                default_impl_id=pick_default_impl_id(impl_list),
                impls=[
                    ImplOut(
                        id=i.id,
                        abstract_id=i.abstract_id,
                        variant_key=i.variant_key,
                        contract_md=i.contract_md,
                    )
                    for i in sorted(impl_list, key=lambda x: x.variant_key)
                ],
            )
        )

    # --- impl_nodes: ONLY representative impls for visible abstracts
    rep_impl_ids: set[UUID] = set(rep_impl_by_visible_abs.values())

    impl_nodes_out = [
        ImplOut(
            id=i.id,
            abstract_id=i.abstract_id,
            variant_key=i.variant_key,
            contract_md=i.contract_md,
        )
        for i in impls_all
        if i.id in rep_impl_ids
    ]

    # Add virtual impls
    impl_nodes_out.extend(virtual_impls_out)

    return GraphOut(
        abstract_nodes=abs_out,
        impl_nodes=impl_nodes_out,
        edges=rewritten_edges,
        related_edges=rewritten_related,
        boundary_hints=[],
    )
