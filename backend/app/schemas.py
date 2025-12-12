from __future__ import annotations

from uuid import UUID
from pydantic import BaseModel, Field
from typing import Optional


class NodeOut(BaseModel):
    id: UUID
    slug: str
    title: str
    summary: str | None = None


class EdgeOut(BaseModel):
    id: UUID
    source: UUID
    target: UUID
    type: str
    rank: int | None = None


class RelatedOut(BaseModel):
    a: UUID
    b: UUID


class GraphOut(BaseModel):
    nodes: list[NodeOut]
    edges: list[EdgeOut]
    related: list[RelatedOut]

class NodeCreateIn(BaseModel):
    slug: str = Field(min_length=1, max_length=120)
    title: str = Field(min_length=1, max_length=200)
    summary: Optional[str] = Field(default=None, max_length=500)

class NodeCreateOut(BaseModel):
    node: NodeOut
