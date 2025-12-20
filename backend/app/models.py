from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    CheckConstraint,
    exists,
    select,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.dialects.postgresql import ENUM as PG_ENUM
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import aliased


class Base(DeclarativeBase):
    pass


ABSTRACT_NODE_KIND_PG = PG_ENUM(
    "concept",
    "group",
    name="abstract_node_kind",
    create_type=False
)


class AbstractNodeKind(str, enum.Enum):
    concept = "concept"
    group = "group"


class AbstractNode(Base):
    __tablename__ = "abstract_nodes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(200))
    short_title: Mapped[str] = mapped_column(String(30), unique=True)
    summary: Mapped[str | None] = mapped_column(String(500), nullable=True)
    body_md: Mapped[str | None] = mapped_column(Text, nullable=True)

    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("abstract_nodes.id", ondelete="SET NULL"), nullable=True, index=True
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    parent: Mapped["AbstractNode | None"] = relationship(remote_side=[id], foreign_keys=[parent_id])
    impls: Mapped[list["ImplNode"]] = relationship(
        back_populates="abstract", cascade="all, delete-orphan"
    )

    kind: Mapped[AbstractNodeKind] = mapped_column(
        ABSTRACT_NODE_KIND_PG,
        nullable=False,
        server_default="concept",
    )

    @hybrid_property
    def has_children(self) -> bool:
        return len(self.children) > 0  # type: ignore[attr-defined]

    @has_children.expression
    def has_children(cls):
        child = aliased(AbstractNode)
        return exists(select(1).where(child.parent_id == cls.id))

    @hybrid_property
    def has_variants(self) -> bool:
        return len(self.impls) > 1

    @has_variants.expression
    def has_variants(cls):
        return (
            select(func.count(ImplNode.id) > 1)  # type: ignore[name-defined]
            .where(ImplNode.abstract_id == cls.id)  # type: ignore[name-defined]
            .scalar_subquery()
        )


class AbstractMembership(Base):
    """
    Secondary membership of an abstract (usually a concept) in a hub group.
    This is what makes Fourier appear inside multiple hubs without lying in taxonomy.
    """
    __tablename__ = "abstract_memberships"
    __table_args__ = (
        UniqueConstraint("abstract_id", "hub_id", name="uq_membership_abstract_hub"),
        CheckConstraint("abstract_id <> hub_id", name="ck_membership_no_self"),
    )

    abstract_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("abstract_nodes.id", ondelete="CASCADE"),
        primary_key=True,
    )
    hub_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("abstract_nodes.id", ondelete="CASCADE"),
        primary_key=True,
    )

    role: Mapped[str] = mapped_column(String(20), default="member")
    weight: Mapped[int] = mapped_column(Integer, default=1)


class ImplNode(Base):
    __tablename__ = "impl_nodes"
    __table_args__ = (
        UniqueConstraint("abstract_id", "variant_key", name="uq_impl_abstract_variant"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    abstract_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("abstract_nodes.id", ondelete="CASCADE"), index=True
    )

    variant_key: Mapped[str] = mapped_column(String(60), default="core")
    contract_md: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    abstract: Mapped["AbstractNode"] = relationship(back_populates="impls")

    outgoing: Mapped[list["Edge"]] = relationship(
        back_populates="src", foreign_keys="Edge.src_impl_id", cascade="all, delete-orphan"
    )
    incoming: Mapped[list["Edge"]] = relationship(
        back_populates="dst", foreign_keys="Edge.dst_impl_id", cascade="all, delete-orphan"
    )


class EdgeType(str, enum.Enum):
    requires = "requires"
    recommended = "recommended"


class Edge(Base):
    __tablename__ = "edges"
    __table_args__ = (
        UniqueConstraint("src_impl_id", "dst_impl_id", "type", name="uq_edge_src_dst_type"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    src_impl_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("impl_nodes.id", ondelete="CASCADE"), index=True
    )
    dst_impl_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("impl_nodes.id", ondelete="CASCADE"), index=True
    )

    type: Mapped[EdgeType] = mapped_column(Enum(EdgeType, name="edge_type"))
    rank: Mapped[int | None] = mapped_column(Integer, nullable=True)

    src: Mapped["ImplNode"] = relationship(back_populates="outgoing", foreign_keys=[src_impl_id])
    dst: Mapped["ImplNode"] = relationship(back_populates="incoming", foreign_keys=[dst_impl_id])


class RelatedEdge(Base):
    __tablename__ = "related_edges"
    __table_args__ = (
        UniqueConstraint("a_id", "b_id", name="uq_related_pair"),
        CheckConstraint("a_id < b_id", name="ck_related_canonical_order"),
    )

    a_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("abstract_nodes.id", ondelete="CASCADE"), primary_key=True
    )
    b_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("abstract_nodes.id", ondelete="CASCADE"), primary_key=True
    )


class ImplContext(Base):
    __tablename__ = "impl_contexts"

    impl_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("impl_nodes.id", ondelete="CASCADE"),
        primary_key=True,
    )

    context_abstract_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("abstract_nodes.id", ondelete="CASCADE"),
        primary_key=True,
    )
