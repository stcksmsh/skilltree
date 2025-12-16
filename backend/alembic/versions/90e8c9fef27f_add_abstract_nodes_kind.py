"""add abstract_nodes.kind

Revision ID: 90e8c9fef27f
Revises: afd23a9c97f8
Create Date: 2025-12-15 23:55:23.621540

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ENUM

# revision identifiers, used by Alembic.
revision: str = '90e8c9fef27f'
down_revision: Union[str, Sequence[str], None] = 'afd23a9c97f8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade():
    # Create enum type once
    kind_enum = ENUM("concept", "group", name="abstract_node_kind")
    kind_enum.create(op.get_bind(), checkfirst=True)

    op.add_column(
        "abstract_nodes",
        sa.Column(
            "kind",
            kind_enum,
            nullable=False,
            server_default="concept",
        ),
    )

    # optional: drop server_default if you want the app to always set it
    op.alter_column("abstract_nodes", "kind", server_default=None)


def downgrade():
    kind_enum = ENUM("concept", "group", name="abstract_node_kind")
    op.drop_column("abstract_nodes", "kind")

    # drop the enum type
    kind_enum.drop(op.get_bind(), checkfirst=True)
