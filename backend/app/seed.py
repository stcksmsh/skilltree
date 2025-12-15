from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Node, Edge, RelatedEdge, EdgeType
from .logic.graph import would_create_cycle


async def seed_minimal(session: AsyncSession) -> None:
    # wipe (MVP convenience)
    await session.execute(delete(RelatedEdge))
    await session.execute(delete(Edge))
    await session.execute(delete(Node))
    await session.commit()

    def n(slug: str, title: str, short_title: str, summary: str = "") -> Node:
        return Node(slug=slug, title=title, short_title=short_title, summary=summary or None)

    nodes = [
        n("logic", "Logic", "Logic", "Propositional + predicate logic basics."),
        n("sets", "Set Theory", "Sets", "Sets, functions, relations."),
        n("proofs", "Proof Techniques", "Proofs", "Induction, contradiction, construction."),
        n("discrete", "Discrete Mathematics", "Discrete", "Core discrete structures."),
        n("lin-alg", "Linear Algebra", "LinAlg", "Vector spaces, matrices."),
        n("calc", "Calculus", "Calc", "Limits, derivatives, integrals."),
    ]

    session.add_all(nodes)
    await session.flush()  # get IDs

    by_slug = {x.slug: x for x in nodes}

    # requires_pairs are (prereq_slug, topic_slug) and are stored as prereq -> topic
    requires_pairs = [
        ("logic", "proofs"),
        ("sets", "discrete"),
        ("proofs", "discrete"),
        ("lin-alg", "calc"),
    ]


    # insert requires with cycle check
    existing: list[tuple] = []
    for s, t in requires_pairs:
        src = by_slug[s].id
        dst = by_slug[t].id
        if would_create_cycle(existing, (src, dst)):
            raise RuntimeError(f"Seed would create cycle: {s} -> {t}")
        session.add(Edge(src_id=src, dst_id=dst, type=EdgeType.requires, rank=None))
        existing.append((src, dst))

    # recommended (ordered)
    session.add_all(
        [
            Edge(src_id=by_slug["discrete"].id, dst_id=by_slug["lin-alg"].id, type=EdgeType.recommended, rank=1),
            Edge(src_id=by_slug["proofs"].id, dst_id=by_slug["sets"].id, type=EdgeType.recommended, rank=2),
        ]
    )

    # related (canonical order enforced by ck constraint)
    a = by_slug["logic"].id
    b = by_slug["sets"].id
    if a > b:
        a, b = b, a
    session.add(RelatedEdge(a_id=a, b_id=b))

    await session.commit()
