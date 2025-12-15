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
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class EdgeType(str, enum.Enum):
    requires = "requires"
    recommended = "recommended"


class Node(Base):
    __tablename__ = "nodes"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(200))
    short_title: Mapped[str] = mapped_column(String(30), unique=True)
    summary: Mapped[str | None] = mapped_column(String(500), nullable=True)
    body_md: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    outgoing: Mapped[list["Edge"]] = relationship(
        back_populates="src", foreign_keys="Edge.src_id", cascade="all, delete-orphan"
    )
    incoming: Mapped[list["Edge"]] = relationship(
        back_populates="dst", foreign_keys="Edge.dst_id", cascade="all, delete-orphan"
    )


class Edge(Base):
    __tablename__ = "edges"
    __table_args__ = (
        UniqueConstraint("src_id", "dst_id", "type", name="uq_edge_src_dst_type"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    src_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("nodes.id", ondelete="CASCADE"), index=True)
    dst_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("nodes.id", ondelete="CASCADE"), index=True)

    type: Mapped[EdgeType] = mapped_column(Enum(EdgeType, name="edge_type"))
    # only meaningful for recommended edges
    rank: Mapped[int | None] = mapped_column(Integer, nullable=True)

    src: Mapped["Node"] = relationship(back_populates="outgoing", foreign_keys=[src_id])
    dst: Mapped["Node"] = relationship(back_populates="incoming", foreign_keys=[dst_id])


class RelatedEdge(Base):
    __tablename__ = "related_edges"
    __table_args__ = (
        UniqueConstraint("a_id", "b_id", name="uq_related_pair"),
        CheckConstraint("a_id < b_id", name="ck_related_canonical_order"),
    )

    a_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("nodes.id", ondelete="CASCADE"), primary_key=True)
    b_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("nodes.id", ondelete="CASCADE"), primary_key=True)
