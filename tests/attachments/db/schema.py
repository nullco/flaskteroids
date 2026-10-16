import sqlalchemy as sa

from flaskteroids.schema import Snapshot

snapshot = Snapshot()
metadata = snapshot.metadata
snapshot.create_table(
    "documents",
    sa.Column("id", sa.Integer(), primary_key=True),
    sa.Column("title", sa.String()),
    sa.Column("owner_id", sa.Integer()),
    sa.Column("created_at", sa.DateTime()),
    sa.Column("updated_at", sa.DateTime()),
)
