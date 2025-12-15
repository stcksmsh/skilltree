"""add short_title to nodes

Revision ID: c38c02a7307b
Revises: 8e5e5500c166
Create Date: 2025-12-15 19:23:23.602304

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c38c02a7307b'
down_revision: Union[str, Sequence[str], None] = '8e5e5500c166'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.add_column(
        "nodes",
        sa.Column("short_title", sa.String(length=30), nullable=True)
    )

    # backfill from title (truncate safely)
    op.execute("""
        UPDATE nodes
        SET short_title = LEFT(title, 30)
        WHERE short_title IS NULL
    """)

    op.alter_column("nodes", "short_title", nullable=False)



def downgrade():
    op.drop_column("nodes", "short_title")
