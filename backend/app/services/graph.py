# services/graph.py
from __future__ import annotations

import uuid as _uuid
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..models import AbstractNode, AbstractMembership, ImplNode, Edge, RelatedEdge
from ..schemas import GraphOut, AbstractNodeOut, ImplOut, EdgeOut, RelatedEdgeOut


async def build_graph(session: AsyncSession) -> GraphOut:
    """
    Baseline graph (hub-level, membership-aware):

    Definitions:
    - "Top-level domains" = AbstractNode where parent_id IS NULL and kind == "group".
      These are NOT shown in baseline.
    - "Visible hubs" (baseline nodes) =
        A) any AbstractNode whose parent_id is a top-level domain id (depth-2),
           regardless of kind (group or concept)
        B) any true root concept: parent_id IS NULL and kind == "concept" (optional)

    Membership:
    - An abstract can belong to one or more hubs via AbstractMembership (abstract_id -> hub_id).
      This supports "Fourier is in Methods but also appears in DSP/Physics hubs".

    Edge aggregation:
    - We aggregate impl->impl edges up to hub->hub edges by expanding:
        src_hubs = {home_hub(src_abstract)} ∪ memberships(src_abstract)
        dst_hubs = {home_hub(dst_abstract)} ∪ memberships(dst_abstract)
      and then counting/merging into a single EdgeOut per (src_hub, dst_hub, type).
    - Recommended rank is min(rank) across merged edges.

    Payload:
    - abstract_nodes: visible hubs only
    - impl_nodes: exactly ONE representative impl per visible hub (default impl if exists, else virtual)
      so UI can map impl->abstract.
    - edges: aggregated hub-level edges using representative impl ids.
    - related_edges: omitted (empty) for baseline.
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

    # memberships (for baseline has_children + hub mapping)
    memberships_all = (await session.execute(select(AbstractMembership))).scalars().all()

    abs_by_id: dict[UUID, AbstractNode] = {}
    child_count_by_id: dict[UUID, int] = {}
    impl_count_by_id: dict[UUID, int] = {}

    for a, child_count, impl_count in abs_rows:
        abs_by_id[a.id] = a
        child_count_by_id[a.id] = int(child_count or 0)
        impl_count_by_id[a.id] = int(impl_count or 0)

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
    visible_depth2: set[UUID] = {
        a.id for a in abs_by_id.values()
        if a.parent_id is not None and a.parent_id in top_domain_ids
    }

    visible_root_concepts: set[UUID] = {
        a.id for a in abs_by_id.values()
        if a.parent_id is None and kind_str(a) == "concept"
    }

    visible_abs_ids: set[UUID] = visible_depth2 | visible_root_concepts

    # ---------- membership maps ----------
    # abs -> hubs it belongs to
    member_hubs_by_abs: dict[UUID, set[UUID]] = {}
    # hub -> member count (for baseline has_children)
    member_count_by_hub: dict[UUID, int] = {}

    for m in memberships_all:
        # only count memberships to visible hubs (expected)
        if m.hub_id in visible_abs_ids:
            member_hubs_by_abs.setdefault(m.abstract_id, set()).add(m.hub_id)
            member_count_by_hub[m.hub_id] = member_count_by_hub.get(m.hub_id, 0) + 1

    # ---------- taxonomy "home hub" representative ----------
    rep_cache: dict[UUID, UUID | None] = {}

    def home_hub(abs_id: UUID) -> UUID | None:
        """
        Climb taxonomy until we hit a visible hub/root-concept. If none, return None.
        """
        if abs_id in rep_cache:
            return rep_cache[abs_id]

        cur = abs_by_id.get(abs_id)
        while cur is not None:
            if cur.id in visible_abs_ids:
                rep_cache[abs_id] = cur.id
                return cur.id

            if cur.parent_id is None:
                break

            cur = abs_by_id.get(cur.parent_id)

        rep_cache[abs_id] = None
        return None

    def hubs_for_abstract(abs_id: UUID) -> set[UUID]:
        """
        Hub set for an abstract = {home_hub} ∪ memberships(abs).
        Filtered to visible hubs.
        """
        out: set[UUID] = set()

        h = home_hub(abs_id)
        if h is not None and h in visible_abs_ids:
            out.add(h)

        for mh in member_hubs_by_abs.get(abs_id, set()):
            if mh in visible_abs_ids:
                out.add(mh)

        return out

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

    # ---------- aggregate edges to hub-level ----------
    impl_by_id: dict[UUID, ImplNode] = {i.id: i for i in impls_all}

    # key: (srcHubAbsId, dstHubAbsId, type) -> rankMin (or None)
    agg: dict[tuple[UUID, UUID, str], int | None] = {}

    for e in edges_all:
        src_impl = impl_by_id.get(e.src_impl_id)
        dst_impl = impl_by_id.get(e.dst_impl_id)
        if not src_impl or not dst_impl:
            continue

        src_hubs = hubs_for_abstract(src_impl.abstract_id)
        dst_hubs = hubs_for_abstract(dst_impl.abstract_id)
        if not src_hubs or not dst_hubs:
            continue

        etype = e.type.value if hasattr(e.type, "value") else str(e.type)

        for sh in src_hubs:
            for dh in dst_hubs:
                if sh == dh:
                    continue

                key = (sh, dh, etype)
                if etype == "recommended":
                    cur = agg.get(key)
                    rank = e.rank
                    if rank is None:
                        # keep existing
                        if cur is None:
                            agg[key] = None
                    else:
                        if cur is None:
                            agg[key] = rank
                        else:
                            agg[key] = rank if cur is None else min(cur, rank)
                else:
                    # requires: ignore rank
                    if key not in agg:
                        agg[key] = None

    # deterministic EdgeOut ids per aggregated key
    def edge_id_for(sh: UUID, dh: UUID, etype: str) -> UUID:
        return _uuid.uuid5(_VIRTUAL_NS, f"baseline-edge:{etype}:{sh}:{dh}")

    rewritten_edges: list[EdgeOut] = []
    for (sh, dh, etype), rank_min in sorted(agg.items(), key=lambda x: (str(x[0][0]), str(x[0][1]), x[0][2])):
        src_rep_impl = rep_impl_by_visible_abs.get(sh)
        dst_rep_impl = rep_impl_by_visible_abs.get(dh)
        if src_rep_impl is None or dst_rep_impl is None:
            continue

        rewritten_edges.append(
            EdgeOut(
                id=edge_id_for(sh, dh, etype),
                src_impl_id=src_rep_impl,
                dst_impl_id=dst_rep_impl,
                type=etype,
                rank=rank_min if etype == "recommended" else None,
            )
        )

    # ---------- pack visible abstract nodes ----------
    abs_out: list[AbstractNodeOut] = []
    for abs_id in sorted(visible_abs_ids, key=lambda x: str(x)):
        a = abs_by_id.get(abs_id)
        if not a:
            continue

        impl_list = impls_by_abs.get(abs_id, [])

        # has_children for baseline should include:
        # - taxonomy children
        # - OR membership members (so hubs drill even if taxonomy is thin)
        has_kids = (child_count_by_id.get(abs_id, 0) > 0) or (member_count_by_hub.get(abs_id, 0) > 0)

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
                has_children=has_kids,
                has_variants=(impl_count_by_id.get(abs_id, 0) > 1),
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

    # ---------- impl_nodes: only representative impls for visible hubs ----------
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
        related_edges=[],  # baseline: omit for now
        boundary_hints=[],
    )
