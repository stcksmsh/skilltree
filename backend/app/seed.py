from __future__ import annotations

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from .models import (
    AbstractNode,
    AbstractMembership,
    ImplContext,
    ImplNode,
    Edge,
    RelatedEdge,
    EdgeType,
    AbstractNodeKind,
)
from .logic.graph import would_create_cycle


async def seed_minimal(session: AsyncSession) -> None:
    # wipe (MVP convenience)
    await session.execute(delete(RelatedEdge))
    await session.execute(delete(Edge))
    await session.execute(delete(ImplContext))
    await session.execute(delete(AbstractMembership))
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

    def member(concept: AbstractNode, hub: AbstractNode, role: str = "member", weight: int = 1) -> AbstractMembership:
        return AbstractMembership(abstract_id=concept.id, hub_id=hub.id, role=role, weight=weight)

    # -------------------------
    # Top-level domains (NOT shown on baseline)
    # -------------------------
    math = a("math", "Math", "Math", kind=AbstractNodeKind.group, summary="Mathematics domain.")
    physics = a("physics", "Physics", "Phys", kind=AbstractNodeKind.group, summary="Physics domain.")
    dsp = a("signals", "Signal Processing", "DSP", kind=AbstractNodeKind.group, summary="DSP domain.")
    session.add_all([math, physics, dsp])
    await session.flush()

    # -------------------------
    # Hubs (depth-2 groups; shown on baseline)
    # -------------------------
    # Math hubs
    methods = a("math-methods", "Methods", "Methods", kind=AbstractNodeKind.group, parent=math)
    linalg_h = a("linear-algebra", "Linear Algebra", "LinAlg", kind=AbstractNodeKind.group, parent=math)
    calc_h = a("calculus", "Calculus", "Calc", kind=AbstractNodeKind.group, parent=math)
    prob_h = a("probability", "Probability", "Prob", kind=AbstractNodeKind.group, parent=math)
    opt_h = a("optimization", "Optimization", "Opt", kind=AbstractNodeKind.group, parent=math)

    # Physics hubs
    qm_h = a("qm-tools", "QM Toolkit", "QMTools", kind=AbstractNodeKind.group, parent=physics)
    waves_h = a("waves-signals", "Waves & Signals", "Waves", kind=AbstractNodeKind.group, parent=physics)

    # DSP hubs
    ss_h = a("signals-systems", "Signals & Systems", "S&S", kind=AbstractNodeKind.group, parent=dsp)
    filt_h = a("filters", "Filters", "Filt", kind=AbstractNodeKind.group, parent=dsp)

    session.add_all([methods, linalg_h, calc_h, prob_h, opt_h, qm_h, waves_h, ss_h, filt_h])
    await session.flush()

    # -------------------------
    # Concepts (children of hubs)
    # -------------------------
    # Methods
    complex_numbers = a("complex", "Complex Numbers", "Cpx", parent=methods)
    ode = a("ode", "ODEs", "ODE", parent=methods)
    pde = a("pde", "PDEs", "PDE", parent=methods)

    # Linear algebra
    vectors = a("vectors", "Vectors", "Vec", parent=linalg_h)
    matrices = a("matrices", "Matrices", "Mat", parent=linalg_h)
    eigen = a("eigen", "Eigenvalues & Eigenvectors", "Eigen", parent=linalg_h)

    # Calculus
    limits = a("limits", "Limits", "Lim", parent=calc_h)
    derivatives = a("derivatives", "Derivatives", "Deriv", parent=calc_h)
    integrals = a("integrals", "Integrals", "Int", parent=calc_h)

    # Probability
    rv = a("random-variables", "Random Variables", "RV", parent=prob_h)
    distributions = a("distributions", "Distributions", "Distr", parent=prob_h)

    # Optimization
    grad = a("gradients", "Gradients", "Grad", parent=opt_h)
    least_squares = a("least-squares", "Least Squares", "LSQ", parent=opt_h)

    # Fourier (taxonomy home: Methods)
    fourier = a("fourier-transform", "Fourier Transform", "Fourier", parent=methods)

    # Physics QM toolkit
    hilbert = a("hilbert-spaces", "Hilbert Spaces", "Hilbert", parent=qm_h)
    operators = a("operators", "Operators", "Ops", parent=qm_h)
    qm_intro = a("quantum-mechanics", "Quantum Mechanics", "QM", parent=qm_h)

    # Physics Waves
    wave_eq = a("wave-equation", "Wave Equation", "WaveEq", parent=waves_h)
    spectra = a("spectra", "Spectra", "Spect", parent=waves_h)

    # DSP hubs
    convolution = a("convolution", "Convolution", "Conv", parent=ss_h)
    frequency_response = a("freq-response", "Frequency Response", "H(w)", parent=ss_h)
    sampling = a("sampling", "Sampling", "Samp", parent=ss_h)

    fir = a("fir", "FIR Filters", "FIR", parent=filt_h)
    iir = a("iir", "IIR Filters", "IIR", parent=filt_h)

    session.add_all([
        complex_numbers, ode, pde,
        vectors, matrices, eigen,
        limits, derivatives, integrals,
        rv, distributions,
        grad, least_squares,
        fourier,
        hilbert, operators, qm_intro,
        wave_eq, spectra,
        convolution, frequency_response, sampling,
        fir, iir
    ])
    await session.flush()

    # -------------------------
    # Memberships (Fourier is shared across hubs)
    # -------------------------
    session.add_all([
        member(fourier, methods, role="portal", weight=10),
        member(fourier, ss_h, role="portal", weight=10),
        member(fourier, waves_h, role="portal", weight=10),
        member(fourier, qm_h, role="portal", weight=10),
    ])
    await session.flush()

    # -------------------------
    # Impl nodes
    # -------------------------
    # core impls for normal concepts
    impls = {}

    def add_core(n: AbstractNode):
        impls[n.slug] = impl(n, "core")

    for n in [
        complex_numbers, ode, pde,
        vectors, matrices, eigen,
        limits, derivatives, integrals,
        rv, distributions,
        grad, least_squares,
        hilbert, operators, qm_intro,
        wave_eq, spectra,
        convolution, frequency_response, sampling,
        fir, iir
    ]:
        add_core(n)

    # Fourier variants (no core, to enforce context selection)
    ft_math = impl(fourier, "math")
    ft_signals = impl(fourier, "signals")
    ft_physics = impl(fourier, "physics")

    session.add_all(list(impls.values()) + [ft_math, ft_signals, ft_physics])
    await session.flush()

    # Variant activation contexts
    session.add_all([
        ImplContext(impl_id=ft_math.id, context_abstract_id=methods.id),
        ImplContext(impl_id=ft_math.id, context_abstract_id=calc_h.id),
        ImplContext(impl_id=ft_math.id, context_abstract_id=linalg_h.id),

        ImplContext(impl_id=ft_signals.id, context_abstract_id=ss_h.id),
        ImplContext(impl_id=ft_signals.id, context_abstract_id=filt_h.id),

        ImplContext(impl_id=ft_physics.id, context_abstract_id=waves_h.id),
        ImplContext(impl_id=ft_physics.id, context_abstract_id=qm_h.id),
    ])
    await session.flush()

    # -------------------------
    # Edges (impl -> impl)
    # -------------------------
    requires_pairs = [
        # Methods prerequisites
        (impls["complex"].id if "complex" in impls else impls["complex_numbers"].id, impls["ode"].id),  # may not exist; keep below robust
    ]
    # robustly build pairs by exact slugs
    def I(slug: str) -> ImplNode:
        return impls[slug]

    requires_pairs = [
        # linear algebra / calc chain
        (I("vectors").id, I("matrices").id),
        (I("matrices").id, I("eigen").id),

        (I("limits").id, I("derivatives").id),
        (I("derivatives").id, I("integrals").id),

        # optimization uses calc + linalg
        (I("derivatives").id, I("gradients").id),
        (I("matrices").id, I("least-squares").id),
        (I("gradients").id, I("least-squares").id),

        # DSP: convolution -> freq response -> sampling -> Fourier(signals)
        (I("convolution").id, I("freq-response").id),
        (I("freq-response").id, I("sampling").id),
        (I("sampling").id, ft_signals.id),

        # Physics: wave eq -> spectra -> Fourier(physics)
        (I("wave-equation").id, I("spectra").id),
        (I("spectra").id, ft_physics.id),

        # QM: hilbert -> operators -> QM intro -> Fourier(physics) (toy)
        (I("hilbert-spaces").id, I("operators").id),
        (I("operators").id, I("quantum-mechanics").id),
        (I("quantum-mechanics").id, ft_physics.id),

        # math formulation supports signals formulation (optional)
        (ft_math.id, ft_signals.id),
    ]

    existing: list[tuple] = []
    for src, dst in requires_pairs:
        if would_create_cycle(existing, (src, dst)):
            raise RuntimeError(f"Seed would create cycle: {src} -> {dst}")
        session.add(Edge(src_impl_id=src, dst_impl_id=dst, type=EdgeType.requires, rank=None))
        existing.append((src, dst))

    # recommended edges
    session.add_all([
        Edge(src_impl_id=I("integrals").id, dst_impl_id=ft_math.id, type=EdgeType.recommended, rank=1),
        Edge(src_impl_id=I("eigen").id, dst_impl_id=ft_math.id, type=EdgeType.recommended, rank=2),
    ])

    await session.commit()
