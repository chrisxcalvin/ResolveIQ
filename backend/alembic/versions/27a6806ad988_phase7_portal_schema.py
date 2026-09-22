"""phase7 portal schema

Revision ID: 27a6806ad988
Revises: cde3df1b3603
Create Date: 2026-09-22 17:41:29.475417

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '27a6806ad988'
down_revision: Union[str, Sequence[str], None] = 'cde3df1b3603'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Phase 7 customer portal: seeded demo customers need a human-presentable
    # name + account reference for the picker UI. Real agent-side customers
    # keep these NULL — the portal's customer-list endpoint scopes itself to
    # `display_name IS NOT NULL`, so this doubles as the boundary that keeps
    # real customer data out of the public demo surface.
    op.add_column("customers", sa.Column("display_name", sa.String(), nullable=True))
    op.add_column("customers", sa.Column("account_reference", sa.String(), nullable=True))

    # Fast-path: high-confidence, non-account-specific drafts get flagged so
    # the agent queue can surface them for one-click approval (see
    # app/decision/decide.py). A visibility flag on the existing "drafted"
    # status, not a new ticket_status enum value — avoids an ALTER TYPE
    # migration for something that's purely a UI prioritization signal.
    op.add_column(
        "ticket_drafts",
        sa.Column("fast_path_eligible", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("ticket_drafts", "fast_path_eligible")
    op.drop_column("customers", "account_reference")
    op.drop_column("customers", "display_name")
