from __future__ import annotations

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from .models import (
    AbstractNode,
    ImplNode,
    Edge,
    RelatedEdge,
    EdgeType,
    AbstractNodeKind,
)
from .logic.graph import would_create_cycle


async def seed_minimal(session: AsyncSession) -> None:
    # wipe (MVP convenience)
    # order matters due to FKs
    await session.execute(delete(RelatedEdge))
    await session.execute(delete(Edge))
    await session.execute(delete(ImplNode))
    await session.execute(delete(AbstractNode))
    await session.commit()

    def a(
        slug: str,
        title: str,
        short_title: str,
        *,
        kind: AbstractNodeKind = AbstractNodeKind.concept,
        parent: AbstractNode | None = None,
        summary: str = "",
        body_md: str | None = None,
    ) -> AbstractNode:
        return AbstractNode(
            slug=slug,
            title=title,
            short_title=short_title,
            summary=summary or None,
            body_md=body_md,
            kind=kind,
            parent_id=parent.id if parent else None,
        )

    def impl(
        abstract: AbstractNode,
        variant_key: str = "core",
        contract_md: str | None = None,
    ) -> ImplNode:
        return ImplNode(
            abstract_id=abstract.id,
            variant_key=variant_key,
            contract_md=contract_md,
        )

    # -------------------------
    # Hierarchy (abstract nodes)
    # -------------------------
    math = a("math", "Math", "Math", kind=AbstractNodeKind.group, summary="Mathematical foundations.")
    physics = a("physics", "Physics", "Phys", kind=AbstractNodeKind.group, summary="Physics concepts.")
    dsp_group = a("signal-processing", "Signal Processing", "DSP", kind=AbstractNodeKind.group, summary="DSP domain.")

    session.add_all([math, physics, dsp_group])
    await session.flush()  # IDs for parent_id

    # Math children (expandable super-node)
    logic = a("logic", "Logic", "Logic", parent=math, summary="Propositional + predicate logic basics.")
    lin_alg = a("lin-alg", "Linear Algebra", "LinAlg", parent=math, summary="Vector spaces, matrices.")
    calc = a("calc", "Calculus", "Calc", parent=math, summary="Limits, derivatives, integrals.")

    # Fourier: concept with variants (NOT a container)
    fourier = a(
        "fourier-transform",
        "Fourier Transform",
        "Fourier",
        parent=math,
        summary="Frequency-domain representations; multiple formulations.",
    )

    # DSP / Physics children
    s_and_s = a(
        "signals-and-systems",
        "Signals & Systems",
        "S&S",
        parent=dsp_group,
        summary="LTI systems, convolution, frequency response.",
    )
    qm = a(
        "quantum-mechanics",
        "Quantum Mechanics",
        "QM",
        parent=physics,
        summary="Intro QM foundations and tools.",
    )

    session.add_all([logic, lin_alg, calc, fourier, s_and_s, qm])
    await session.flush()

    # -------------------------
    # Impl nodes (DAG lives here)
    # -------------------------
    # core impls for normal concepts
    logic_core = impl(logic, "core")
    la_core = impl(lin_alg, "core")
    calc_core = impl(calc, "core")
    ss_core = impl(s_and_s, "core")
    qm_core = impl(qm, "core")

    # Fourier variants (no core on purpose, to force UI to show variant picker)
    ft_math = impl(fourier, "math", "Rigorous definition, spaces, convergence.")
    ft_signals = impl(fourier, "signals", "DFT/FFT, sampling, aliasing, frequency response usage.")
    ft_physics = impl(fourier, "physics", "Spectral interpretation, waves/operators, physical intuition.")

    session.add_all(
        [logic_core, la_core, calc_core, ss_core, qm_core, ft_math, ft_signals, ft_physics]
    )
    await session.flush()

    # -------------------------
    # Edges (impl -> impl)
    # -------------------------
    # requires edges, cycle-checked
    requires_pairs = [
        (logic_core.id, la_core.id),     # Logic -> Linear Algebra (toy example)
        (la_core.id, calc_core.id),      # Linear Algebra -> Calculus (toy example)
        (ss_core.id, ft_signals.id),     # Signals & Systems -> Fourier (signals)
        (qm_core.id, ft_physics.id),     # Quantum Mechanics -> Fourier (physics)
        (ft_math.id, ft_signals.id),     # optional: math formulation supports signals formulation
    ]

    existing: list[tuple] = []
    for src, dst in requires_pairs:
        if would_create_cycle(existing, (src, dst)):
            raise RuntimeError(f"Seed would create cycle: {src} -> {dst}")
        session.add(Edge(src_impl_id=src, dst_impl_id=dst, type=EdgeType.requires, rank=None))
        existing.append((src, dst))

    # recommended edges (ordered)
    session.add_all(
        [
            Edge(src_impl_id=calc_core.id, dst_impl_id=ft_math.id, type=EdgeType.recommended, rank=1),
            Edge(src_impl_id=la_core.id, dst_impl_id=ft_math.id, type=EdgeType.recommended, rank=2),
        ]
    )

    # -------------------------
    # Related edges (abstract <-> abstract)
    # -------------------------
    a_id = logic.id
    b_id = lin_alg.id
    if a_id > b_id:
        a_id, b_id = b_id, a_id
    session.add(RelatedEdge(a_id=a_id, b_id=b_id))

    await session.commit()
