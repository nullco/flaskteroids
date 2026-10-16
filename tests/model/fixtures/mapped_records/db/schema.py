import sqlalchemy as sa

from flaskteroids.schema import Snapshot

snapshot = Snapshot()
metadata = snapshot.metadata
snapshot.create_table(
    "authors",
    sa.Column("id", sa.Integer(), primary_key=True),
    sa.Column("name", sa.String(), nullable=False),
    sa.Column("age", sa.Integer()),
    sa.Column("active", sa.Boolean()),
    sa.Column("password_digest", sa.String()),
    sa.Column("created_at", sa.DateTime()),
    sa.Column("updated_at", sa.DateTime()),
)
snapshot.create_table(
    "posts",
    sa.Column("id", sa.Integer(), primary_key=True),
    sa.Column("title", sa.String(), nullable=False),
    sa.Column("author_id", sa.Integer(), sa.ForeignKey("authors.id"), nullable=False),
)
