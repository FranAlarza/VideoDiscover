"""Create download persistence tables."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260720_01"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "downloads",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("platform", sa.String(length=20), nullable=False),
        sa.Column("media_id", sa.String(length=200), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("canonical_url", sa.String(length=2048), nullable=False),
        sa.Column("output_type", sa.String(length=10), nullable=False),
        sa.Column("video_quality", sa.Integer(), nullable=True),
        sa.Column("audio_bitrate", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_downloads_created_at", "downloads", ["created_at"])
    op.create_table(
        "download_attempts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("download_id", sa.String(length=36), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("percentage", sa.Float(), nullable=True),
        sa.Column("downloaded_bytes", sa.Integer(), nullable=True),
        sa.Column("total_bytes", sa.Integer(), nullable=True),
        sa.Column("speed_bytes_per_second", sa.Float(), nullable=True),
        sa.Column("eta_seconds", sa.Integer(), nullable=True),
        sa.Column("failure_code", sa.String(length=100), nullable=True),
        sa.Column("failure_message", sa.String(length=500), nullable=True),
        sa.Column("result_filename", sa.String(length=500), nullable=True),
        sa.Column("result_extension", sa.String(length=20), nullable=True),
        sa.Column("result_size_bytes", sa.Integer(), nullable=True),
        sa.Column("result_effective_quality", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["download_id"], ["downloads.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_attempts_status_created",
        "download_attempts",
        ["status", "created_at"],
    )
    op.create_index(
        "uq_attempt_download_number",
        "download_attempts",
        ["download_id", "number"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_attempt_download_number", table_name="download_attempts")
    op.drop_index("ix_attempts_status_created", table_name="download_attempts")
    op.drop_table("download_attempts")
    op.drop_index("ix_downloads_created_at", table_name="downloads")
    op.drop_table("downloads")
