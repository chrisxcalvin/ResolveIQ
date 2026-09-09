"""day2 schema adjustments

Revision ID: cde3df1b3603
Revises: 33a0b53a8053
Create Date: 2026-08-09 13:43:42.044388

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'cde3df1b3603'
down_revision: Union[str, Sequence[str], None] = '33a0b53a8053'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Switching to local sentence-transformers (all-MiniLM-L6-v2, 384 dims)
    # instead of the OpenAI-shaped placeholder from migration 0001. Table is
    # still empty at this point, so no data-loss/cast concern.
    op.execute("ALTER TABLE kb_chunks ALTER COLUMN embedding TYPE vector(384)")

    # Retrieval needs to filter/boost by category (TRD section 2) but
    # kb_documents never had one.
    op.add_column("kb_documents", sa.Column("category", sa.String(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("kb_documents", "category")
    op.execute("ALTER TABLE kb_chunks ALTER COLUMN embedding TYPE vector(1536)")
