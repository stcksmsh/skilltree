"""add abstract_memberships table

Revision ID: 94916d19a7f7
Revises: 22b3bbda7c30
Create Date: 2025-12-20 01:56:32.383500

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '94916d19a7f7'
down_revision: Union[str, Sequence[str], None] = '22b3bbda7c30'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "abstract_memberships",
        sa.Column("abstract_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("hub_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False, server_default="member"),
        sa.Column("weight", sa.Integer(), nullable=False, server_default="1"),
        sa.ForeignKeyConstraint(["abstract_id"], ["abstract_nodes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["hub_id"], ["abstract_nodes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("abstract_id", "hub_id"),
        sa.CheckConstraint("abstract_id <> hub_id", name="ck_membership_no_self"),
    )
    op.create_index("ix_abstract_memberships_hub_id", "abstract_memberships", ["hub_id"])
    op.create_index("ix_abstract_memberships_abstract_id", "abstract_memberships", ["abstract_id"])


def downgrade() -> None:
    op.drop_index("ix_abstract_memberships_abstract_id", table_name="abstract_memberships")
    op.drop_index("ix_abstract_memberships_hub_id", table_name="abstract_memberships")
    op.drop_table("abstract_memberships")