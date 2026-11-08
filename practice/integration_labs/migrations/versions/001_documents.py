"""Create the document store and recorded answers."""
from alembic import op
import sqlalchemy as sa

revision = "001"
down_revision = None


def upgrade():
    op.create_table("documents", sa.Column("tenant_id", sa.String(), primary_key=True),
                    sa.Column("source_id", sa.String(), primary_key=True),
                    sa.Column("title", sa.String(), nullable=False),
                    sa.Column("section", sa.String(), nullable=False),
                    sa.Column("version", sa.String(), nullable=False),
                    sa.Column("valid_from", sa.String(), nullable=False),
                    sa.Column("valid_to", sa.String(), nullable=True),
                    sa.Column("text", sa.Text(), nullable=False))
    op.create_table("answers", sa.Column("id", sa.String(), primary_key=True),
                    sa.Column("tenant_id", sa.String(), nullable=False),
                    sa.Column("payload", sa.JSON(), nullable=False))
    op.create_index("ix_answers_tenant_id", "answers", ["tenant_id"])


def downgrade():
    op.drop_table("answers")
    op.drop_table("documents")
