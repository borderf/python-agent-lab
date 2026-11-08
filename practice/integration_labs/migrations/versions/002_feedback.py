"""Add feedback while retaining documents and answers from revision 001."""
from alembic import op
import sqlalchemy as sa

revision = "002"
down_revision = "001"


def upgrade():
    op.create_table("feedback", sa.Column("id", sa.String(), primary_key=True),
                    sa.Column("answer_id", sa.String(), nullable=False),
                    sa.Column("tenant_id", sa.String(), nullable=False),
                    sa.Column("helpful", sa.Boolean(), nullable=False),
                    sa.Column("note", sa.Text(), nullable=False))
    op.create_index("ix_feedback_answer_id", "feedback", ["answer_id"])


def downgrade():
    op.drop_table("feedback")
