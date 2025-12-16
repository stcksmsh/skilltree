from __future__ import annotations

from operator import or_
from uuid import UUID
from fastapi.middleware.cors import CORSMiddleware
from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .db import get_session
from .models import AbstractNode, ImplNode, Edge, RelatedEdge, ImplContext
from .schemas import GraphOut, AbstractNodeOut, ImplOut, EdgeOut, RelatedEdgeOut, BoundaryHintOut, NodeCreateIn
from .seed import seed_minimal


app = FastAPI(title="SkillTree MVP")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"ok": True}


@app.post("/api/admin/seed")
async def admin_seed(session: AsyncSession = Depends(get_session)):
    # MVP: no auth; delete later
    await seed_minimal(session)
    return {"seeded": True}


@app.get("/api/graph", response_model=GraphOut)
async def get_graph(session: AsyncSession = Depends(get_session)):
    # counts for has_children
    children_cte = (
        select(AbstractNode.parent_id.label("id"), func.count().label("child_count"))
        .where(AbstractNode.parent_id.isnot(None))
        .group_by(AbstractNode.parent_id)
        .cte("children_cte")
    )

    # counts for has_variants
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

    impls = (await session.execute(select(ImplNode))).scalars().all()
    edges = (await session.execute(select(Edge))).scalars().all()
    related = (await session.execute(select(RelatedEdge))).scalars().all()

    def pick_default_impl_id(impl_list: list[ImplNode]) -> UUID | None:
        if not impl_list:
            return None
        core = next((x for x in impl_list if x.variant_key == "core"), None)
        if core:
            return core.id
        return sorted(impl_list, key=lambda x: x.variant_key)[0].id

    abs_out: list[AbstractNodeOut] = []
    for a, child_count, impl_count in abs_rows:
        impl_list = list(a.impls or [])
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
                has_children=child_count > 0,
                has_variants=impl_count > 1,
                default_impl_id=pick_default_impl_id(impl_list),
                impls=[
                    ImplOut(
                        id=i.id,
                        abstract_id=i.abstract_id,
                        variant_key=i.variant_key,
                        contract_md=i.contract_md,
                    )
                    for i in impl_list
                ],
            )
        )

    return GraphOut(
        abstract_nodes=abs_out,
        impl_nodes=[
            ImplOut(id=i.id, abstract_id=i.abstract_id, variant_key=i.variant_key, contract_md=i.contract_md)
            for i in impls
        ],
        edges=[
            EdgeOut(id=e.id, src_impl_id=e.src_impl_id, dst_impl_id=e.dst_impl_id, type=e.type.value, rank=e.rank)
            for e in edges
        ],
        related_edges=[RelatedEdgeOut(a_id=r.a_id, b_id=r.b_id) for r in related],
        boundary_hints=[],
    )



@app.post("/api/nodes", status_code=503)
async def create_node(payload: NodeCreateIn, session: AsyncSession = Depends(get_session)):
    return HTTPException(status_code=503, detail="Not implemented yet")


@app.get("/api/graph/focus/{abstract_id}", response_model=GraphOut)
async def get_graph_focus(
    abstract_id: UUID,
    session: AsyncSession = Depends(get_session),
):
    # ---------- 1) focus ----------
    focus = await session.get(AbstractNode, abstract_id)
    if not focus:
        raise HTTPException(status_code=404, detail="Abstract node not found")

    # ---------- 2) inside abstracts: focus + direct children ----------
    children = (
        await session.execute(
            select(AbstractNode).where(AbstractNode.parent_id == abstract_id)
        )
    ).scalars().all()

    inside_abs: list[AbstractNode] = [focus, *children]
    inside_abs_ids: set[UUID] = {n.id for n in inside_abs}

    # ---------- 3) focus context chain (focus + ancestors) ----------
    # This defines “context applicability” for impls via impl_contexts.
    focus_ctx_ids: set[UUID] = set()
    cur = focus
    while True:
        focus_ctx_ids.add(cur.id)
        if cur.parent_id is None:
            break
        parent = await session.get(AbstractNode, cur.parent_id)
        if not parent:
            break
        cur = parent

    # ---------- 4) inside impls ----------
    inside_impls = (
        await session.execute(
            select(ImplNode).where(ImplNode.abstract_id.in_(inside_abs_ids))
        )
    ).scalars().all()

    inside_impl_ids: set[UUID] = {i.id for i in inside_impls}

    # ---------- 5) touching edges (edges that touch inside impls) ----------
    touching_edges = (
        await session.execute(
            select(Edge).where(
                or_(
                    Edge.src_impl_id.in_(inside_impl_ids),
                    Edge.dst_impl_id.in_(inside_impl_ids),
                )
            )
        )
    ).scalars().all()

    # If no edges, return the inside subgraph immediately
    if not touching_edges:
        # gather impl counts for has_variants
        impl_counts = dict(
            (
                await session.execute(
                    select(ImplNode.abstract_id, func.count(ImplNode.id))
                    .where(ImplNode.abstract_id.in_(inside_abs_ids))
                    .group_by(ImplNode.abstract_id)
                )
            ).all()
        )

        abs_id_to_impls: dict[UUID, list[ImplNode]] = {}
        for i in inside_impls:
            abs_id_to_impls.setdefault(i.abstract_id, []).append(i)

        def pick_default_impl_id(impls: list[ImplNode]) -> UUID | None:
            if not impls:
                return None
            core = next((x for x in impls if x.variant_key == "core"), None)
            return core.id if core else sorted(impls, key=lambda x: x.variant_key)[0].id

        abstract_nodes_out = [
            AbstractNodeOut(
                id=n.id,
                slug=n.slug,
                title=n.title,
                short_title=n.short_title,
                summary=n.summary,
                body_md=n.body_md,
                kind=n.kind,
                parent_id=n.parent_id,
                has_children=(n.id == abstract_id and len(children) > 0),
                has_variants=(impl_counts.get(n.id, 0) > 1),
                default_impl_id=pick_default_impl_id(abs_id_to_impls.get(n.id, [])),
                impls=[
                    ImplOut(
                        id=i.id,
                        abstract_id=i.abstract_id,
                        variant_key=i.variant_key,
                        contract_md=i.contract_md,
                    )
                    for i in abs_id_to_impls.get(n.id, [])
                ],
            )
            for n in inside_abs
        ]

        return GraphOut(
            abstract_nodes=abstract_nodes_out,
            impl_nodes=[
                ImplOut(id=i.id, abstract_id=i.abstract_id, variant_key=i.variant_key, contract_md=i.contract_md)
                for i in inside_impls
            ],
            edges=[],
            related_edges=[],
            boundary_hints=[],
        )

    # ---------- 6) load impls referenced by touching edges (for mapping) ----------
    edge_impl_ids: set[UUID] = set()
    for e in touching_edges:
        edge_impl_ids.add(e.src_impl_id)
        edge_impl_ids.add(e.dst_impl_id)

    edge_impls = (
        await session.execute(select(ImplNode).where(ImplNode.id.in_(edge_impl_ids)))
    ).scalars().all()

    impl_by_id: dict[UUID, ImplNode] = {i.id: i for i in edge_impls}
    impl_to_abs: dict[UUID, UUID] = {i.id: i.abstract_id for i in edge_impls}

    # ---------- 7) load abstracts for those impl endpoints (and ancestors for boundary grouping) ----------
    endpoint_abs_ids = set(impl_to_abs.values())

    endpoint_abstracts = (
        await session.execute(select(AbstractNode).where(AbstractNode.id.in_(endpoint_abs_ids)))
    ).scalars().all()

    abs_by_id: dict[UUID, AbstractNode] = {a.id: a for a in endpoint_abstracts}

    # preload ancestors for all endpoint abstracts so boundary grouping won’t KeyError
    missing_parent_ids: set[UUID] = set()
    for a in endpoint_abstracts:
        if a.parent_id and a.parent_id not in abs_by_id:
            missing_parent_ids.add(a.parent_id)

    while missing_parent_ids:
        parents = (
            await session.execute(select(AbstractNode).where(AbstractNode.id.in_(missing_parent_ids)))
        ).scalars().all()

        missing_parent_ids.clear()
        for p in parents:
            abs_by_id[p.id] = p
            if p.parent_id and p.parent_id not in abs_by_id:
                missing_parent_ids.add(p.parent_id)

    def collect_ancestor_ids(node: AbstractNode) -> set[UUID]:
        ids: set[UUID] = set()
        cur = node
        while True:
            ids.add(cur.id)
            if cur.parent_id is None:
                break
            cur = abs_by_id[cur.parent_id]
        return ids

    focus_ancestor_ids = collect_ancestor_ids(focus)

    def find_boundary_group(outside_abs: AbstractNode) -> AbstractNode:
        cur = outside_abs

        # climb up as long as the parent is NOT in the focus ancestor chain
        while cur.parent_id is not None and cur.parent_id not in focus_ancestor_ids:
            cur = abs_by_id[cur.parent_id]

        # `cur` is now the topmost node in its branch that is still outside the focus ancestor chain
        # Optional: enforce returning a group if your UI expects groups only
        if cur.kind != 'group':
            # walk up until group or root (still outside focus chain due to loop stop condition)
            tmp = cur
            while tmp.parent_id is not None and tmp.parent_id not in focus_ancestor_ids:
                tmp = abs_by_id[tmp.parent_id]
                if tmp.kind == 'group':
                    return tmp
        return cur


    # ---------- 8) prerequisite impls: requires edges from inside -> outside ----------
    # NOTE: this is the corrected direction
    candidate_prereq_impl_ids: set[UUID] = set()
    for e in touching_edges:
        if e.type != 'requires':
            continue
        if e.src_impl_id in inside_impl_ids:
            candidate_prereq_impl_ids.add(e.dst_impl_id)

    # ---------- 9) filter prerequisite impls by context applicability via impl_contexts ----------
    prereq_impl_ids: set[UUID] = set()
    if candidate_prereq_impl_ids:
        applicable_impl_ids = set(
            (
                await session.execute(
                    select(ImplContext.impl_id)
                    .where(ImplContext.impl_id.in_(candidate_prereq_impl_ids))
                    .where(ImplContext.context_abstract_id.in_(focus_ctx_ids))
                )
            ).scalars().all()
        )
        prereq_impl_ids = applicable_impl_ids

    # Only include prereq abstracts if the abstract is a concept (your rule)
    prereq_abs_ids: set[UUID] = set()
    for iid in prereq_impl_ids:
        abs_id = impl_to_abs.get(iid)
        if not abs_id:
            continue
        a = abs_by_id.get(abs_id)
        if a and a.kind == 'concept':
            prereq_abs_ids.add(abs_id)

    # ---------- 10) final included sets ----------
    all_abs_ids: set[UUID] = set(inside_abs_ids) | set(prereq_abs_ids)

    # load prereq abstracts not already in inside
    prereq_abs: list[AbstractNode] = []
    if prereq_abs_ids:
        prereq_abs = (
            await session.execute(select(AbstractNode).where(AbstractNode.id.in_(prereq_abs_ids)))
        ).scalars().all()

    all_abs: list[AbstractNode] = inside_abs + [a for a in prereq_abs if a.id not in inside_abs_ids]

    # included impls: all inside impls + the prereq impl endpoints
    included_impl_ids: set[UUID] = set(inside_impl_ids) | set(prereq_impl_ids)

    included_impls = (
        await session.execute(select(ImplNode).where(ImplNode.id.in_(included_impl_ids)))
    ).scalars().all()

    # ---------- 11) edges to return (only those whose endpoints are both included impls) ----------
    edges_out = [
        e for e in touching_edges
        if e.src_impl_id in included_impl_ids and e.dst_impl_id in included_impl_ids
    ]

    # ---------- 12) boundary hints ----------
    boundary_map: dict[tuple[UUID, str], int] = {}
    for e in touching_edges:
        sa = impl_to_abs[e.src_impl_id]
        da = impl_to_abs[e.dst_impl_id]

        sa_in = sa in all_abs_ids
        da_in = da in all_abs_ids

        if sa_in ^ da_in:
            outside_abs = abs_by_id[da if sa_in else sa]
            boundary_group = find_boundary_group(outside_abs)
            key = (boundary_group.id, e.type)
            boundary_map[key] = boundary_map.get(key, 0) + 1

    boundary_hints = [
        BoundaryHintOut(
            group_id=gid,
            title=abs_by_id[gid].title,
            short_title=abs_by_id[gid].short_title,
            type=edge_type.value,
            count=count,
        )
        for (gid, edge_type), count in boundary_map.items()
    ]

    # ---------- 13) has_variants computation (real, not local) ----------
    impl_counts = dict(
        (
            await session.execute(
                select(ImplNode.abstract_id, func.count(ImplNode.id))
                .where(ImplNode.abstract_id.in_(all_abs_ids))
                .group_by(ImplNode.abstract_id)
            )
        ).all()
    )

    # group included impls by abstract for AbstractNodeOut.impls
    abs_id_to_impls: dict[UUID, list[ImplNode]] = {}
    for i in included_impls:
        abs_id_to_impls.setdefault(i.abstract_id, []).append(i)

    def pick_default_impl_id(impls: list[ImplNode]) -> UUID | None:
        if not impls:
            return None
        core = next((x for x in impls if x.variant_key == "core"), None)
        return core.id if core else sorted(impls, key=lambda x: x.variant_key)[0].id

    abstract_nodes_out = [
        AbstractNodeOut(
            id=n.id,
            slug=n.slug,
            title=n.title,
            short_title=n.short_title,
            summary=n.summary,
            body_md=n.body_md,
            kind=n.kind,
            parent_id=n.parent_id,
            has_children=(n.id == abstract_id and any(c.parent_id == abstract_id for c in children)),
            has_variants=(impl_counts.get(n.id, 0) > 1),
            default_impl_id=pick_default_impl_id(abs_id_to_impls.get(n.id, [])),
            impls=[
                ImplOut(
                    id=i.id,
                    abstract_id=i.abstract_id,
                    variant_key=i.variant_key,
                    contract_md=i.contract_md,
                )
                for i in abs_id_to_impls.get(n.id, [])
            ],
        )
        for n in all_abs
    ]

    # related edges optional here; keeping empty for focus view
    return GraphOut(
        abstract_nodes=abstract_nodes_out,
        impl_nodes=[
            ImplOut(id=i.id, abstract_id=i.abstract_id, variant_key=i.variant_key, contract_md=i.contract_md)
            for i in included_impls
        ],
        edges=[
            EdgeOut(
                id=e.id,
                src_impl_id=e.src_impl_id,
                dst_impl_id=e.dst_impl_id,
                type=e.type.value,
                rank=e.rank,
            )
            for e in edges_out
        ],
        related_edges=[],
        boundary_hints=boundary_hints,
    )
