"""add impl_contexts table

Revision ID: 22b3bbda7c30
Revises: 90e8c9fef27f
Create Date: 2025-12-16 01:41:30.266087

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision: str = '22b3bbda7c30'
down_revision: Union[str, Sequence[str], None] = '90e8c9fef27f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.create_table(
        "impl_contexts",
        sa.Column(
            "impl_id",
            UUID(as_uuid=True),
            sa.ForeignKey("impl_nodes.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "context_abstract_id",
            UUID(as_uuid=True),
            sa.ForeignKey("abstract_nodes.id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )

    op.create_index(
        "ix_impl_contexts_context",
        "impl_contexts",
        ["context_abstract_id"],
    )


def downgrade():
    op.drop_index("ix_impl_contexts_context", table_name="impl_contexts")
    op.drop_table("impl_contexts")
