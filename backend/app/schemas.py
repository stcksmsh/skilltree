from __future__ import annotations

from uuid import UUID
from pydantic import BaseModel, Field
from typing import Optional


class AbstractNodeOut(BaseModel):
    id: UUID
    slug: str
    title: str
    short_title: str
    summary: Optional[str] = None
    body_md: Optional[str] = None

    kind: str  # or Literal[...] / Enum
    parent_id: Optional[UUID] = None

    has_children: bool
    has_variants: bool

    default_impl_id: Optional[UUID] = None
    impls: list[ImplOut] = []

class ImplOut(BaseModel):
    id: UUID
    abstract_id: UUID
    variant_key: str
    contract_md: Optional[str] = None

class EdgeOut(BaseModel):
    id: UUID
    src_impl_id: UUID
    dst_impl_id: UUID
    type: str
    rank: int | None = None


class RelatedEdgeOut(BaseModel):
    a_id: UUID
    b_id: UUID


class GraphOut(BaseModel):
    abstract_nodes: list[AbstractNodeOut]
    impl_nodes: list[ImplOut]
    edges: list[EdgeOut]
    related_edges: list[RelatedEdgeOut]

class NodeCreateIn(BaseModel):
    slug: str = Field(min_length=1, max_length=120)
    title: str = Field(min_length=1, max_length=200)
    short_title: str = Field(min_length=1, max_length=30)
    summary: Optional[str] = Field(default=None, max_length=500)
