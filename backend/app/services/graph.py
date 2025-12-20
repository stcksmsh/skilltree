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
    Collapsed baseline graph (domain-top items):

    - Top-level domain groups (parent_id IS NULL AND kind=group) are NOT shown.
    - Visible baseline nodes:
        A) "Domain-top items": any abstract whose parent is a top-level domain group (depth=2),
           regardless of kind (concept or group).
        B) True root concepts: parent_id IS NULL AND kind=concept (optional, if you have any).

    - Representative of any abstract:
        - If it is visible: itself
        - Else: climb up until you find a visible ancestor (typically the depth-2 item under a domain).
               If you hit a domain/root without finding one: None (drop it from baseline)

    - impl_nodes includes exactly one representative impl per visible abstract
      (virtual impl if none exists), so the UI can map impl->abstract.
    - edges are rewritten to connect representative impls of representative abstracts.
    - related_edges are omitted for baseline (can add later if you want).
    """

    # ---------- load all abstracts + counts ----------
    children_cte = (
        select(AbstractNode.parent_id.label("id"), func.count().label("child_count"))
        .where(AbstractNode.parent_id.isnot(None))
        .group_by(AbstractNode.parent_id)
        .cte("children_cte")
    )

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
        .options(selectinload(AbstractNode.impls))
    )

    abs_rows = (await session.execute(q_abs)).all()

    impls_all = (await session.execute(select(ImplNode))).scalars().all()
    edges_all = (await session.execute(select(Edge))).scalars().all()

    abs_by_id: dict[UUID, AbstractNode] = {}
    child_count_by_id: dict[UUID, int] = {}
    impl_count_by_id: dict[UUID, int] = {}

    for a, child_count, impl_count in abs_rows:
        abs_by_id[a.id] = a
        child_count_by_id[a.id] = int(child_count or 0)
        impl_count_by_id[a.id] = int(impl_count or 0)

    # ---------- kind helper ----------
    def kind_str(a: AbstractNode) -> str:
        k = getattr(a, "kind", None)
        if k is None:
            return ""
        return k.value if hasattr(k, "value") else str(k)

    # ---------- identify top-level domain groups (not shown) ----------
    top_domain_ids: set[UUID] = {
        a.id for a in abs_by_id.values()
        if a.parent_id is None and kind_str(a) == "group"
    }

    # ---------- visible baseline nodes ----------
    # A) depth-2 under domain (parent is a top-level domain group)
    visible_depth2: set[UUID] = {
        a.id for a in abs_by_id.values()
        if a.parent_id is not None and a.parent_id in top_domain_ids
    }

    # B) true root concepts (rare / optional)
    visible_root_concepts: set[UUID] = {
        a.id for a in abs_by_id.values()
        if a.parent_id is None and kind_str(a) == "concept"
    }

    visible_abs_ids: set[UUID] = visible_depth2 | visible_root_concepts

    # ---------- collapse to visible representative ----------
    rep_cache: dict[UUID, UUID | None] = {}

    def rep(abs_id: UUID) -> UUID | None:
        if abs_id in rep_cache:
            return rep_cache[abs_id]

        cur = abs_by_id.get(abs_id)
        while cur is not None:
            if cur.id in visible_abs_ids:
                rep_cache[abs_id] = cur.id
                return cur.id

            # if we hit a domain/root and it's not visible, stop
            if cur.parent_id is None:
                break

            cur = abs_by_id.get(cur.parent_id)

        rep_cache[abs_id] = None
        return None

    # ---------- impl grouping ----------
    impls_by_abs: dict[UUID, list[ImplNode]] = {}
    for i in impls_all:
        impls_by_abs.setdefault(i.abstract_id, []).append(i)

    def pick_default_impl_id(impls: list[ImplNode]) -> UUID | None:
        if not impls:
            return None
        core = next((x for x in impls if x.variant_key == "core"), None)
        return core.id if core else sorted(impls, key=lambda x: x.variant_key)[0].id

    # ---------- representative impls per visible abstract ----------
    import uuid as _uuid
    _VIRTUAL_NS = _uuid.UUID("00000000-0000-0000-0000-000000000001")

    def virtual_impl_id(abs_id: UUID) -> UUID:
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
            virtual_impls_out.append(
                ImplOut(
                    id=vid,
                    abstract_id=abs_id,
                    variant_key="__virtual__",
                    contract_md=None,
                )
            )

    # ---------- rewrite edges to representative impl endpoints ----------
    impl_by_id: dict[UUID, ImplNode] = {i.id: i for i in impls_all}

    rewritten_edges: list[EdgeOut] = []
    for e in edges_all:
        src_impl = impl_by_id.get(e.src_impl_id)
        dst_impl = impl_by_id.get(e.dst_impl_id)
        if not src_impl or not dst_impl:
            continue

        src_abs_rep = rep(src_impl.abstract_id)
        dst_abs_rep = rep(dst_impl.abstract_id)

        if src_abs_rep is None or dst_abs_rep is None:
            continue
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

    # ---------- pack visible abstract nodes ----------
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
                kind=kind_str(a),
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
    impl_nodes_out.extend(virtual_impls_out)

    return GraphOut(
        abstract_nodes=abs_out,
        impl_nodes=impl_nodes_out,
        edges=rewritten_edges,
        related_edges=[],
        boundary_hints=[],
    )
