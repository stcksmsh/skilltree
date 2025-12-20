from __future__ import annotations

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from .models import (
    AbstractNode,
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
    # TOP-LEVEL DOMAINS (NOT baseline-visible as nodes in your new baseline builder)
    # -------------------------
    math = a("math", "Mathematics", "Math", kind=AbstractNodeKind.group, summary="Mathematical foundations.")
    physics = a("physics", "Physics", "Phys", kind=AbstractNodeKind.group, summary="Physics foundations.")
    signals = a("signals", "Signals & Systems", "Sig", kind=AbstractNodeKind.group, summary="Signals, systems, DSP.")

    session.add_all([math, physics, signals])
    await session.flush()

    # -------------------------
    # DEPTH-2 AREAS (baseline nodes)
    # -------------------------
    # Math areas
    methods = a("math-methods", "Mathematical Methods", "Methods", kind=AbstractNodeKind.group, parent=math,
                summary="Shared tools used across many domains.")
    algebra = a("math-algebra", "Linear Algebra", "LinAlg", kind=AbstractNodeKind.group, parent=math,
                summary="Vectors, matrices, eigens, SVD.")
    calc = a("math-calc", "Calculus", "Calc", kind=AbstractNodeKind.group, parent=math,
             summary="Derivatives, integrals, ODE/PDE basics.")
    prob = a("math-prob", "Probability", "Prob", kind=AbstractNodeKind.group, parent=math,
             summary="Random variables, expectation, variance, distributions.")
    opt = a("math-opt", "Optimization", "Opt", kind=AbstractNodeKind.group, parent=math,
            summary="Gradient descent, convexity, constrained optimization.")

    # Physics areas
    classical = a("phys-classical", "Classical Mechanics", "CM", kind=AbstractNodeKind.group, parent=physics,
                  summary="Newton/Lagrange basics.")
    em = a("phys-em", "Electromagnetism", "EM", kind=AbstractNodeKind.group, parent=physics,
           summary="Fields, waves, Maxwell overview.")
    qm = a("phys-qm", "Quantum Mechanics", "QM", kind=AbstractNodeKind.group, parent=physics,
           summary="State vectors, operators, Fourier in QM.")
    waves = a("phys-waves", "Waves", "Waves", kind=AbstractNodeKind.group, parent=physics,
              summary="Wave equation, dispersion, Fourier viewpoint.")

    # Signals areas
    ss = a("sig-ss", "Signals & Systems", "S&S", kind=AbstractNodeKind.group, parent=signals,
           summary="LTI systems, convolution, impulse response.")
    dsp = a("sig-dsp", "Digital Signal Processing", "DSP", kind=AbstractNodeKind.group, parent=signals,
            summary="Sampling, FFT, digital filters.")
    comms = a("sig-comms", "Communications", "Comms", kind=AbstractNodeKind.group, parent=signals,
              summary="Modulation, noise, basic channel models.")

    session.add_all([methods, algebra, calc, prob, opt, classical, em, qm, waves, ss, dsp, comms])
    await session.flush()

    # -------------------------
    # CONCEPTS (depth 3+)
    # -------------------------
    # Methods concepts
    fourier = a("fourier-transform", "Fourier Transform", "Fourier", parent=methods,
                summary="Frequency-domain representation; basis for FFT/waves.")
    laplace = a("laplace-transform", "Laplace Transform", "Laplace", parent=methods,
                summary="s-domain analysis; useful for systems/ODEs.")
    complex_nums = a("complex-numbers", "Complex Numbers", "Complex", parent=methods,
                     summary="Euler form, magnitude/phase, complex exponentials.")
    convolution = a("convolution", "Convolution", "Conv", parent=methods,
                    summary="Core operator connecting time and frequency views.")
    dirac = a("dirac-delta", "Dirac Delta", "Delta", parent=methods,
              summary="Impulse modeling; distributions view (informal).")

    # Algebra concepts
    vectors = a("vectors", "Vectors & Spaces", "Vec", parent=algebra, summary="Vector spaces, basis, dimension.")
    matrices = a("matrices", "Matrices", "Mat", parent=algebra, summary="Multiplication, inverse, rank.")
    eigen = a("eigenvalues", "Eigenvalues & Eigenvectors", "Eig", parent=algebra, summary="Diagonalization.")
    svd = a("svd", "Singular Value Decomposition", "SVD", parent=algebra, summary="SVD, PCA link.")
    orth = a("orthogonality", "Orthogonality", "Ortho", parent=algebra, summary="Inner products, projections.")

    # Calc concepts
    limits = a("limits", "Limits", "Lim", parent=calc, summary="Continuity and limits.")
    deriv = a("derivatives", "Derivatives", "d/dx", parent=calc, summary="Derivative rules, chain rule.")
    integ = a("integrals", "Integrals", "∫", parent=calc, summary="Definite integrals, area.")
    ode = a("odes", "Ordinary Differential Equations", "ODE", parent=calc, summary="First/second order ODEs.")
    pde = a("pdes", "Partial Differential Equations", "PDE", parent=calc, summary="Wave/heat equations intro.")

    # Probability concepts
    rv = a("random-variables", "Random Variables", "RV", parent=prob, summary="Discrete/continuous RVs.")
    expv = a("expectation", "Expectation", "E[X]", parent=prob, summary="Linearity, common expectations.")
    var = a("variance", "Variance", "Var", parent=prob, summary="Variance and covariance.")
    normal = a("normal-dist", "Normal Distribution", "N(μ,σ)", parent=prob, summary="Gaussian.")
    clt = a("clt", "Central Limit Theorem", "CLT", parent=prob, summary="Sum of RVs tends to normal.")

    # Optimization concepts
    gd = a("gradient-descent", "Gradient Descent", "GD", parent=opt, summary="Iterative optimization method.")
    convex = a("convexity", "Convexity", "Convex", parent=opt, summary="Convex sets/functions.")
    constraints = a("constraints", "Constraints", "Constr", parent=opt, summary="Equality/inequality constraints.")
    lagrange = a("lagrange-multipliers", "Lagrange Multipliers", "LM", parent=opt, summary="Constrained extrema.")
    least_squares = a("least-squares", "Least Squares", "LS", parent=opt, summary="Regression via minimization.")

    # Classical mechanics concepts
    newton = a("newton-laws", "Newton's Laws", "Newton", parent=classical, summary="Force, motion.")
    energy = a("energy-work", "Energy & Work", "Energy", parent=classical, summary="Conservation, potential.")
    lagrangian = a("lagrangian-mechanics", "Lagrangian Mechanics", "Lagr", parent=classical,
                   summary="Generalized coordinates, Euler–Lagrange.")
    oscillators = a("harmonic-oscillator", "Harmonic Oscillator", "HO", parent=classical, summary="Mass-spring model.")

    # EM concepts
    maxwell = a("maxwell", "Maxwell's Equations", "Mxwl", parent=em, summary="Field equations.")
    em_waves = a("em-waves", "EM Waves", "EMWave", parent=em, summary="Wave solutions to Maxwell.")
    circuits = a("circuits", "Basic Circuits", "Circ", parent=em, summary="RC/RL/RLC basics (light).")

    # QM concepts
    state_vec = a("state-vectors", "State Vectors", "|ψ>", parent=qm, summary="Hilbert space states.")
    operators = a("operators", "Operators", "Op", parent=qm, summary="Observables as operators.")
    schrod = a("schrodinger", "Schrödinger Equation", "Schr", parent=qm, summary="Time evolution PDE/ODE.")
    uncertainty = a("uncertainty", "Uncertainty Principle", "Δ", parent=qm, summary="Non-commuting observables.")

    # Waves concepts
    wave_eq = a("wave-equation", "Wave Equation", "WaveEq", parent=waves, summary="Second-order PDE.")
    dispersion = a("dispersion", "Dispersion", "Disp", parent=waves, summary="Phase/group velocity.")
    modes = a("modes", "Modes & Harmonics", "Modes", parent=waves, summary="Standing waves, harmonics.")

    # Signals & Systems concepts
    lti = a("lti", "LTI Systems", "LTI", parent=ss, summary="Linearity + time-invariance.")
    impulse = a("impulse-response", "Impulse Response", "h(t)", parent=ss, summary="System characterization.")
    freq_resp = a("frequency-response", "Frequency Response", "H(ω)", parent=ss, summary="Response in frequency domain.")

    # DSP concepts
    sampling = a("sampling", "Sampling", "Samp", parent=dsp, summary="Sampling theorem, aliasing.")
    dft = a("dft", "DFT", "DFT", parent=dsp, summary="Discrete Fourier Transform.")
    fft = a("fft", "FFT", "FFT", parent=dsp, summary="Fast Fourier Transform algorithms.")
    fir = a("fir", "FIR Filters", "FIR", parent=dsp, summary="Finite impulse response filters.")
    iir = a("iir", "IIR Filters", "IIR", parent=dsp, summary="Infinite impulse response filters.")
    window = a("windowing", "Windowing", "Win", parent=dsp, summary="Spectral leakage control.")

    # Comms concepts
    noise = a("noise", "Noise", "Noise", parent=comms, summary="Thermal noise, Gaussian model.")
    snr = a("snr", "SNR", "SNR", parent=comms, summary="Signal-to-noise ratio.")
    amfm = a("am-fm", "AM/FM Modulation", "AMFM", parent=comms, summary="Basic analog modulation.")
    qam = a("qam", "QAM", "QAM", parent=comms, summary="Quadrature amplitude modulation.")

    session.add_all([
        fourier, laplace, complex_nums, convolution, dirac,
        vectors, matrices, eigen, svd, orth,
        limits, deriv, integ, ode, pde,
        rv, expv, var, normal, clt,
        gd, convex, constraints, lagrange, least_squares,
        newton, energy, lagrangian, oscillators,
        maxwell, em_waves, circuits,
        state_vec, operators, schrod, uncertainty,
        wave_eq, dispersion, modes,
        lti, impulse, freq_resp,
        sampling, dft, fft, fir, iir, window,
        noise, snr, amfm, qam,
    ])
    await session.flush()

    # -------------------------
    # IMPL NODES
    # -------------------------
    # For most concepts, core impl
    concepts_core = [
        vectors, matrices, eigen, svd, orth,
        limits, deriv, integ, ode, pde,
        rv, expv, var, normal, clt,
        gd, convex, constraints, lagrange, least_squares,
        newton, energy, lagrangian, oscillators,
        maxwell, em_waves, circuits,
        state_vec, operators, schrod, uncertainty,
        wave_eq, dispersion, modes,
        lti, impulse, freq_resp,
        sampling, dft, fft, fir, iir, window,
        noise, snr, amfm, qam,
        laplace, complex_nums, convolution, dirac,
        fourier,  # we'll override variants below (no core)
    ]

    # Build core impls except Fourier (variants-only)
    impl_nodes: list[ImplNode] = []
    core_impl_by_abs: dict[str, ImplNode] = {}

    for c in concepts_core:
        if c.id == fourier.id:
            continue
        node = impl(c, "core")
        impl_nodes.append(node)

    # Fourier variants (no core on purpose)
    ft_math = impl(fourier, "math")
    ft_signals = impl(fourier, "signals")
    ft_physics = impl(fourier, "physics")
    impl_nodes.extend([ft_math, ft_signals, ft_physics])

    session.add_all(impl_nodes)
    await session.flush()

    # Index impls by slug for easier edge wiring
    impl_by_slug: dict[str, ImplNode] = {}

    # rebuild mapping from DB objects
    for node in impl_nodes:
        abs_node = abs_by_id = None  # not needed; just use relationship-free mapping via slug
    # We can map by scanning all ImplNodes and joining to AbstractNodes is too heavy here.
    # Instead, build explicit dicts:
    def find_impl_for(abs_node: AbstractNode, variant: str = "core") -> ImplNode:
        for i in impl_nodes:
            if i.abstract_id == abs_node.id and i.variant_key == variant:
                return i
        raise RuntimeError(f"Missing impl for {abs_node.slug}:{variant}")

    # Fourier contexts
    session.add_all(
        [
            ImplContext(impl_id=ft_math.id, context_abstract_id=math.id),
            ImplContext(impl_id=ft_signals.id, context_abstract_id=signals.id),
            ImplContext(impl_id=ft_physics.id, context_abstract_id=physics.id),
        ]
    )
    await session.flush()

    # -------------------------
    # EDGES (impl -> impl)
    # -------------------------
    existing: list[tuple] = []

    def add_requires(src: ImplNode, dst: ImplNode) -> None:
        nonlocal existing
        pair = (src.id, dst.id)
        if would_create_cycle(existing, pair):
            raise RuntimeError(f"Seed would create cycle: {src.id} -> {dst.id}")
        session.add(Edge(src_impl_id=src.id, dst_impl_id=dst.id, type=EdgeType.requires, rank=None))
        existing.append(pair)

    def add_recommended(src: ImplNode, dst: ImplNode, rank: int) -> None:
        session.add(Edge(src_impl_id=src.id, dst_impl_id=dst.id, type=EdgeType.recommended, rank=rank))

    # --- Math dependencies
    add_requires(find_impl_for(matrices), find_impl_for(vectors))
    add_requires(find_impl_for(eigen), find_impl_for(matrices))
    add_requires(find_impl_for(svd), find_impl_for(matrices))
    add_requires(find_impl_for(orth), find_impl_for(vectors))

    add_requires(find_impl_for(deriv), find_impl_for(limits))
    add_requires(find_impl_for(integ), find_impl_for(deriv))
    add_requires(find_impl_for(ode), find_impl_for(deriv))
    add_requires(find_impl_for(pde), find_impl_for(ode))

    add_requires(find_impl_for(expv), find_impl_for(rv))
    add_requires(find_impl_for(var), find_impl_for(expv))
    add_requires(find_impl_for(clt), find_impl_for(var))
    add_requires(find_impl_for(normal), find_impl_for(rv))

    add_requires(find_impl_for(gd), find_impl_for(deriv))
    add_requires(find_impl_for(least_squares), find_impl_for(matrices))
    add_requires(find_impl_for(lagrange), find_impl_for(deriv))
    add_requires(find_impl_for(lagrange), find_impl_for(constraints))

    # Methods dependencies
    add_requires(find_impl_for(convolution), find_impl_for(integ))
    add_requires(find_impl_for(complex_nums), find_impl_for(vectors))

    # Fourier (variant-specific dependencies)
    # Math Fourier depends on complex numbers + integrals (informally)
    add_requires(ft_math, find_impl_for(complex_nums))
    add_requires(ft_math, find_impl_for(integ))

    # --- Signals & DSP dependencies (use signals Fourier)
    add_requires(find_impl_for(lti), find_impl_for(convolution))
    add_requires(find_impl_for(impulse), find_impl_for(lti))
    add_requires(find_impl_for(freq_resp), find_impl_for(impulse))
    add_requires(find_impl_for(freq_resp), ft_signals)

    add_requires(find_impl_for(sampling), find_impl_for(freq_resp))
    add_requires(find_impl_for(dft), ft_signals)
    add_requires(find_impl_for(fft), find_impl_for(dft))
    add_requires(find_impl_for(fft), ft_signals)
    add_requires(find_impl_for(window), find_impl_for(dft))
    add_requires(find_impl_for(fir), find_impl_for(convolution))
    add_requires(find_impl_for(iir), find_impl_for(laplace))

    # --- Comms dependencies
    add_requires(find_impl_for(noise), find_impl_for(rv))
    add_requires(find_impl_for(snr), find_impl_for(noise))
    add_requires(find_impl_for(qam), find_impl_for(complex_nums))
    add_requires(find_impl_for(qam), find_impl_for(snr))

    # --- Physics dependencies (use physics Fourier)
    add_requires(find_impl_for(newton), find_impl_for(deriv))
    add_requires(find_impl_for(energy), find_impl_for(integ))
    add_requires(find_impl_for(lagrangian), find_impl_for(energy))

    add_requires(find_impl_for(maxwell), find_impl_for(deriv))
    add_requires(find_impl_for(em_waves), find_impl_for(maxwell))
    add_requires(find_impl_for(wave_eq), find_impl_for(pde))
    add_requires(find_impl_for(wave_eq), ft_physics)
    add_requires(find_impl_for(dispersion), find_impl_for(wave_eq))
    add_requires(find_impl_for(modes), ft_physics)

    add_requires(find_impl_for(state_vec), find_impl_for(vectors))
    add_requires(find_impl_for(operators), find_impl_for(matrices))
    add_requires(find_impl_for(schrod), find_impl_for(pde))
    add_requires(find_impl_for(schrod), ft_physics)
    add_requires(find_impl_for(uncertainty), find_impl_for(operators))

    # Recommended (some ordering hints)
    add_recommended(find_impl_for(fft), find_impl_for(window), 1)
    add_recommended(find_impl_for(schrod), find_impl_for(state_vec), 1)
    add_recommended(find_impl_for(state_vec), find_impl_for(operators), 2)

    # Related edges (a few)
    def add_related(x: AbstractNode, y: AbstractNode) -> None:
        a_id, b_id = x.id, y.id
        if a_id > b_id:
            a_id, b_id = b_id, a_id
        session.add(RelatedEdge(a_id=a_id, b_id=b_id))

    add_related(vectors, matrices)
    add_related(fourier, laplace)
    add_related(sampling, dft)

    await session.commit()
