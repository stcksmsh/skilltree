from __future__ import annotations

import uuid
import networkx as nx


def would_create_cycle(existing_requires: list[tuple[uuid.UUID, uuid.UUID]], new_edge: tuple[uuid.UUID, uuid.UUID]) -> bool:
    g = nx.DiGraph()
    g.add_edges_from(existing_requires)
    g.add_edge(*new_edge)
    return not nx.is_directed_acyclic_graph(g)
