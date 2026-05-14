"""add popup_buttons and allowed_upgrade_hosts

Revision ID: 838107a39a3c
Revises:
Create Date: 2026-05-14 06:47:00.000000+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "838107a39a3c"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = ("channel_pack",)
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "cp_upgrade_rules",
        sa.Column("popup_buttons", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
    )
    op.add_column(
        "cp_apps",
        sa.Column(
            "allowed_upgrade_hosts", sa.JSON(), nullable=False, server_default=sa.text("'[]'")
        ),
    )


def downgrade() -> None:
    op.drop_column("cp_apps", "allowed_upgrade_hosts")
    op.drop_column("cp_upgrade_rules", "popup_buttons")
