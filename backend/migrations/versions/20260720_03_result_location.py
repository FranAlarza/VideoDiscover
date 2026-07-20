"""Persist the private output directory for each completed attempt."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260720_03"
down_revision: str | Sequence[str] | None = "20260720_02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "download_attempts",
        sa.Column("result_output_directory", sa.String(length=4096), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("download_attempts", "result_output_directory")
