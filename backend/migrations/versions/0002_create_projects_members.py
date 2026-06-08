"""create projects and project_members

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-08
"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "projects",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column(
            "status",
            sa.Enum("active", "archived", "deleting", name="projectstatus"),
            nullable=False,
            server_default="active",
        ),
        sa.Column(
            "created_by",
            sa.BigInteger,
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_status", "projects", ["status"])

    op.create_table(
        "project_members",
        sa.Column(
            "project_id",
            sa.BigInteger,
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "user_id",
            sa.BigInteger,
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "role",
            sa.Enum("owner", "admin", "editor", "viewer", name="memberrole"),
            nullable=False,
        ),
        sa.Column("joined_at", sa.DateTime, server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_user", "project_members", ["user_id"])


def downgrade() -> None:
    op.drop_table("project_members")
    op.drop_table("projects")
