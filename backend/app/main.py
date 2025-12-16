from __future__ import annotations

from uuid import UUID
from fastapi.middleware.cors import CORSMiddleware
from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .db import get_session
from .models import AbstractNode, ImplNode, Edge, RelatedEdge
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

    def pick_default_impl_id(impl_list: list[ImplNode]) -> uuid.UUID | None:
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
    # ---------- helpers ----------
    def find_boundary_group(outside_abstract: AbstractNode) -> AbstractNode:
        cur = outside_abstract
        while cur.parent_id is not None:
            if cur.parent_id in inside_abs_ids:
                return cur
            cur = abs_by_id[cur.parent_id]
        return cur

    # ---------- 1) focus ----------
    focus = await session.get(AbstractNode, abstract_id)
    if not focus:
        raise HTTPException(status_code=404, detail="Abstract node not found")

    # ---------- 2) hierarchy inside: focus + direct children ----------
    children = (
        await session.execute(
            select(AbstractNode).where(AbstractNode.parent_id == abstract_id)
        )
    ).scalars().all()

    inside_abs: list[AbstractNode] = [focus, *children]
    inside_abs_ids: set[UUID] = {n.id for n in inside_abs}

    # ---------- 3) initial inside impls ----------
    inside_impls = (
        await session.execute(
            select(ImplNode).where(ImplNode.abstract_id.in_(inside_abs_ids))
        )
    ).scalars().all()

    inside_impl_ids: set[UUID] = {i.id for i in inside_impls}

    focus_domain = focus.slug

    # ---------- 4) touching edges ----------
    touching_edges = (
        await session.execute(
            select(Edge).where(
                (Edge.src_impl_id.in_(inside_impl_ids)) |
                (Edge.dst_impl_id.in_(inside_impl_ids))
            )
        )
    ).scalars().all()

    # ---------- 5) impl → abstract lookup ----------
    edge_impl_ids = {e.src_impl_id for e in touching_edges} | {
        e.dst_impl_id for e in touching_edges
    }

    edge_impls = (
        await session.execute(
            select(ImplNode).where(ImplNode.id.in_(edge_impl_ids))
        )
    ).scalars().all()

    impl_by_id: dict[UUID, ImplNode] = {i.id: i for i in edge_impls}
    impl_to_abs: dict[UUID, UUID] = {i.id: i.abstract_id for i in edge_impls}

    abs_ids = set(impl_to_abs.values())

    abstracts = (
        await session.execute(
            select(AbstractNode).where(AbstractNode.id.in_(abs_ids))
        )
    ).scalars().all()

    abs_by_id: dict[UUID, AbstractNode] = {a.id: a for a in abstracts}

    # ---------- 6) preload ancestors ----------
    missing_parent_ids: set[UUID] = set()

    for a in abstracts:
        cur = a
        while cur.parent_id is not None and cur.parent_id not in abs_by_id:
            missing_parent_ids.add(cur.parent_id)
            break

    while missing_parent_ids:
        parents = (
            await session.execute(
                select(AbstractNode).where(AbstractNode.id.in_(missing_parent_ids))
            )
        ).scalars().all()

        missing_parent_ids.clear()

        for p in parents:
            abs_by_id[p.id] = p
            if p.parent_id is not None and p.parent_id not in abs_by_id:
                missing_parent_ids.add(p.parent_id)

    # ---------- 7) impl-level prerequisite detection ----------
    required_impls_by_inside: set[UUID] = set()

    for e in touching_edges:
        if e.src_impl_id in inside_impl_ids:
            required_impls_by_inside.add(e.dst_impl_id)

    # ---------- 8) include leaf prerequisites (impl + variant filtered) ----------
    extra_inside_abs_ids: set[UUID] = set()

    for impl_id in required_impls_by_inside:
        impl = impl_by_id.get(impl_id)
        if not impl:
            continue

        # TEMP RULE: only core variant participates in focus
        if impl.variant_key != focus_domain:
            continue

        abs_id = impl.abstract_id
        if abs_id in inside_abs_ids:
            continue

        candidate = abs_by_id.get(abs_id)
        if candidate and candidate.kind == 'concept':
            extra_inside_abs_ids.add(abs_id)

    if extra_inside_abs_ids:
        extra_abs = (
            await session.execute(
                select(AbstractNode).where(AbstractNode.id.in_(extra_inside_abs_ids))
            )
        ).scalars().all()

        inside_abs.extend(extra_abs)
        inside_abs_ids |= extra_inside_abs_ids

        # re-load impls now that inside expanded
        inside_impls = (
            await session.execute(
                select(ImplNode).where(ImplNode.abstract_id.in_(inside_abs_ids))
            )
        ).scalars().all()
        inside_impl_ids = {i.id for i in inside_impls}

    # ---------- 9) internal edges + boundary hints ----------
    internal_edges: list[Edge] = []
    boundary_map: dict[tuple[UUID, EdgeType], int] = {}

    for e in touching_edges:
        sa = impl_to_abs[e.src_impl_id]
        da = impl_to_abs[e.dst_impl_id]

        sa_in = sa in inside_abs_ids
        da_in = da in inside_abs_ids

        if sa_in and da_in:
            internal_edges.append(e)
            continue

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

    # ---------- 10) impl grouping ----------
    abs_id_to_impls: dict[UUID, list[ImplNode]] = {}
    for i in inside_impls:
        abs_id_to_impls.setdefault(i.abstract_id, []).append(i)

    def pick_default_impl_id(impls: list[ImplNode]) -> UUID | None:
        if not impls:
            return None
        core = next((x for x in impls if x.variant_key == "core"), None)
        return core.id if core else impls[0].id

    # ---------- 11) output ----------
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
            has_variants=(len(abs_id_to_impls.get(n.id, [])) > 1),
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
            ImplOut(
                id=i.id,
                abstract_id=i.abstract_id,
                variant_key=i.variant_key,
                contract_md=i.contract_md,
            )
            for i in inside_impls
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
