from __future__ import annotations

import uuid
from pydantic import BaseModel


class NodeOut(BaseModel):
    id: uuid.UUID
    slug: str
    title: str
    summary: str | None = None


class EdgeOut(BaseModel):
    id: uuid.UUID
    source: uuid.UUID
    target: uuid.UUID
    type: str
    rank: int | None = None


class RelatedOut(BaseModel):
    a: uuid.UUID
    b: uuid.UUID


class GraphOut(BaseModel):
    nodes: list[NodeOut]
    edges: list[EdgeOut]
    related: list[RelatedOut]
