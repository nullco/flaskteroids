import sqlalchemy as sa

from flaskteroids.schema import Snapshot

snapshot = Snapshot()
metadata = snapshot.metadata
snapshot.create_table(
    "authors",
    sa.Column("id", sa.Integer(), primary_key=True),
    sa.Column("name", sa.String()),
    sa.Column("passcode_digest", sa.String()),
    sa.Column("created_at", sa.DateTime()),
    sa.Column("updated_at", sa.DateTime()),
)
snapshot.create_table(
    "stories",
    sa.Column("id", sa.Integer(), primary_key=True),
    sa.Column("title", sa.String()),
    sa.Column("author_id", sa.Integer(), sa.ForeignKey("authors.id")),
    sa.Column("editor_id", sa.Integer(), sa.ForeignKey("authors.id")),
    sa.Column("created_at", sa.DateTime()),
    sa.Column("updated_at", sa.DateTime()),
)
