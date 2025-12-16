"""split nodes into abstract_nodes + impl_nodes

Revision ID: afd23a9c97f8
Revises: c38c02a7307b
Create Date: 2025-12-15 23:25:53.105063

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, ENUM

# revision identifiers, used by Alembic.
revision: str = 'afd23a9c97f8'
down_revision: Union[str, Sequence[str], None] = 'c38c02a7307b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade():
    # 1) Create abstract_nodes (new)
    op.create_table(
        "abstract_nodes",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("slug", sa.String(length=120), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("short_title", sa.String(length=30), nullable=False),
        sa.Column("summary", sa.String(length=500), nullable=True),
        sa.Column("body_md", sa.Text(), nullable=True),
        sa.Column("parent_id", UUID(as_uuid=True), sa.ForeignKey("abstract_nodes.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_abstract_nodes_slug", "abstract_nodes", ["slug"], unique=True)
    op.create_index("ix_abstract_nodes_parent_id", "abstract_nodes", ["parent_id"], unique=False)
    op.create_index("ix_abstract_nodes_short_title", "abstract_nodes", ["short_title"], unique=True)

    # 2) Create impl_nodes
    op.create_table(
        "impl_nodes",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("abstract_id", UUID(as_uuid=True), sa.ForeignKey("abstract_nodes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("variant_key", sa.String(length=60), nullable=False, server_default="core"),
        sa.Column("contract_md", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("abstract_id", "variant_key", name="uq_impl_abstract_variant"),
    )
    op.create_index("ix_impl_nodes_abstract_id", "impl_nodes", ["abstract_id"], unique=False)

    # 3) Create new edges table layout (same name "edges" but different columns)
    # We'll rename old edges first to avoid name collision.
    op.rename_table("edges", "edges_old")
    op.drop_constraint(
        "uq_edge_src_dst_type",
        "edges_old",
        type_="unique",
    )


    op.create_table(
        "edges",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("src_impl_id", UUID(as_uuid=True), sa.ForeignKey("impl_nodes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("dst_impl_id", UUID(as_uuid=True), sa.ForeignKey("impl_nodes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("type", ENUM(name="edge_type", create_type=False), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=True),
        sa.UniqueConstraint("src_impl_id", "dst_impl_id", "type", name="uq_edge_src_dst_type"),
    )
    op.create_index("ix_edges_src_impl_id", "edges", ["src_impl_id"], unique=False)
    op.create_index("ix_edges_dst_impl_id", "edges", ["dst_impl_id"], unique=False)

    # 4) related_edges references nodes.id currently; rename + recreate with abstract FK
    op.rename_table("related_edges", "related_edges_old")
    op.drop_constraint(
        "uq_related_pair",
        "related_edges_old",
        type_="unique",
    )
    op.create_table(
        "related_edges",
        sa.Column("a_id", UUID(as_uuid=True), sa.ForeignKey("abstract_nodes.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("b_id", UUID(as_uuid=True), sa.ForeignKey("abstract_nodes.id", ondelete="CASCADE"), primary_key=True),
        sa.UniqueConstraint("a_id", "b_id", name="uq_related_pair"),
        sa.CheckConstraint("a_id < b_id", name="ck_related_canonical_order"),
    )

    # 5) Move nodes -> abstract_nodes (keep same IDs)
    op.rename_table("nodes", "nodes_old")

    op.execute("""
        INSERT INTO abstract_nodes (id, slug, title, short_title, summary, body_md, parent_id, created_at, updated_at)
        SELECT id, slug, title, short_title, summary, body_md, NULL, created_at, updated_at
        FROM nodes_old
    """)

    # 6) Create default impl ("core") for each abstract node
    op.execute("""
        INSERT INTO impl_nodes (id, abstract_id, variant_key, contract_md, created_at, updated_at)
        SELECT gen_random_uuid(), id, 'core', NULL, created_at, updated_at
        FROM abstract_nodes
    """)

    # 7) Migrate old edges: node->node becomes impl(core)->impl(core)
    # Join via abstract_id and variant_key='core'
    op.execute("""
        INSERT INTO edges (id, src_impl_id, dst_impl_id, type, rank)
        SELECT
            gen_random_uuid(),
            s_impl.id,
            d_impl.id,
            e.type,
            e.rank
        FROM edges_old e
        JOIN impl_nodes s_impl ON s_impl.abstract_id = e.src_id AND s_impl.variant_key = 'core'
        JOIN impl_nodes d_impl ON d_impl.abstract_id = e.dst_id AND d_impl.variant_key = 'core'
    """)

    # 8) Migrate related_edges (IDs are the same, now point to abstract_nodes)
    op.execute("""
        INSERT INTO related_edges (a_id, b_id)
        SELECT a_id, b_id
        FROM related_edges_old
    """)

    # 9) Drop old tables
    op.drop_table("edges_old")
    op.drop_table("related_edges_old")
    op.drop_table("nodes_old")


def downgrade():
    # Reverse: recreate nodes, edges in old form; collapse each abstract into its core impl edges.

    op.create_table(
        "nodes",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("slug", sa.String(length=120), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("short_title", sa.String(length=30), nullable=False),
        sa.Column("summary", sa.String(length=500), nullable=True),
        sa.Column("body_md", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_nodes_slug", "nodes", ["slug"], unique=True)
    op.create_index("ix_nodes_short_title", "nodes", ["short_title"], unique=True)

    op.create_table(
        "edges_old",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("src_id", UUID(as_uuid=True), sa.ForeignKey("nodes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("dst_id", UUID(as_uuid=True), sa.ForeignKey("nodes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("type", ENUM(name="edge_type", create_type=False), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=True),
        sa.UniqueConstraint("src_id", "dst_id", "type", name="uq_edge_src_dst_type"),
    )
    op.create_index("ix_edges_old_src_id", "edges_old", ["src_id"], unique=False)
    op.create_index("ix_edges_old_dst_id", "edges_old", ["dst_id"], unique=False)

    op.create_table(
        "related_edges_old",
        sa.Column("a_id", UUID(as_uuid=True), sa.ForeignKey("nodes.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("b_id", UUID(as_uuid=True), sa.ForeignKey("nodes.id", ondelete="CASCADE"), primary_key=True),
        sa.UniqueConstraint("a_id", "b_id", name="uq_related_pair"),
        sa.CheckConstraint("a_id < b_id", name="ck_related_canonical_order"),
    )

    # abstract_nodes -> nodes
    op.execute("""
        INSERT INTO nodes (id, slug, title, short_title, summary, body_md, created_at, updated_at)
        SELECT id, slug, title, short_title, summary, body_md, created_at, updated_at
        FROM abstract_nodes
    """)

    # edges impl->impl collapse to abstract->abstract using core impls only
    op.execute("""
        INSERT INTO edges_old (id, src_id, dst_id, type, rank)
        SELECT
            gen_random_uuid(),
            s.abstract_id,
            d.abstract_id,
            e.type,
            e.rank
        FROM edges e
        JOIN impl_nodes s ON s.id = e.src_impl_id AND s.variant_key = 'core'
        JOIN impl_nodes d ON d.id = e.dst_impl_id AND d.variant_key = 'core'
    """)

    # related_edges stays same ids -> nodes
    op.execute("""
        INSERT INTO related_edges_old (a_id, b_id)
        SELECT a_id, b_id
        FROM related_edges
    """)

    # swap tables back
    op.drop_table("edges")
    op.rename_table("edges_old", "edges")

    op.drop_table("related_edges")
    op.rename_table("related_edges_old", "related_edges")

    op.drop_table("impl_nodes")
    op.drop_index("ix_abstract_nodes_slug", table_name="abstract_nodes")
    op.drop_index("ix_abstract_nodes_parent_id", table_name="abstract_nodes")
    op.drop_index("ix_abstract_nodes_short_title", table_name="abstract_nodes")
    op.drop_table("abstract_nodes")
