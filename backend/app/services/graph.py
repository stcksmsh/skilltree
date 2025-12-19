from __future__ import annotations

from uuid import UUID
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..models import AbstractNode, ImplNode, Edge, RelatedEdge
from ..schemas import GraphOut, AbstractNodeOut, ImplOut, EdgeOut, RelatedEdgeOut


async def build_graph(session: AsyncSession):
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
