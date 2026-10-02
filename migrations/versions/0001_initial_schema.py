"""Create initial camera and capture tables.

Revision ID: 0001_initial_schema
"""

import sqlalchemy as sa
from alembic import op

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "cameras",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("device_key", sa.String(), nullable=False, unique=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("hardware_reference", sa.String(), nullable=True),
        sa.Column("os_platform", sa.String(), nullable=False),
        sa.Column("first_seen_at_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_connected", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("capabilities_json", sa.Text(), nullable=True),
    )
    op.create_table(
        "captures",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "camera_id",
            sa.String(),
            sa.ForeignKey("cameras.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("file_name", sa.String(), nullable=False),
        sa.Column("relative_path", sa.String(), nullable=False),
        sa.Column("created_at_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at_local", sa.String(), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("image_format", sa.String(), nullable=False),
        sa.Column("file_size_bytes", sa.Integer(), nullable=True),
        sa.Column("focus_value", sa.Integer(), nullable=True),
        sa.Column("exposure", sa.Integer(), nullable=True),
        sa.Column("gain", sa.Integer(), nullable=True),
        sa.Column("white_balance", sa.Integer(), nullable=True),
        sa.Column("brightness", sa.Integer(), nullable=True),
        sa.Column("extra_params_json", sa.Text(), nullable=True),
        sa.Column("capture_duration_ms", sa.Integer(), nullable=True),
        sa.Column("capture_mode", sa.String(), nullable=False),
        sa.Column("sha256", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "status IN ('captured', 'missing', 'deleted', 'failed')",
            name="ck_captures_status",
        ),
    )
    op.create_index("ix_captures_created_at_utc", "captures", ["created_at_utc"])
    op.create_index("ix_captures_camera_id", "captures", ["camera_id"])
    op.create_index("ix_captures_status", "captures", ["status"])
    op.create_table(
        "settings",
        sa.Column("key", sa.String(), primary_key=True),
        sa.Column("value", sa.Text(), nullable=True),
        sa.Column("updated_at_utc", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("settings")
    op.drop_index("ix_captures_status", table_name="captures")
    op.drop_index("ix_captures_camera_id", table_name="captures")
    op.drop_index("ix_captures_created_at_utc", table_name="captures")
    op.drop_table("captures")
    op.drop_table("cameras")
