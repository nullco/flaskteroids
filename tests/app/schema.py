import sqlalchemy as sa

from flaskteroids.schema import Snapshot

snapshot = Snapshot()
metadata = snapshot.metadata
snapshot.create_table(
    "users",
    sa.Column("id", sa.Integer(), primary_key=True),
    sa.Column("username", sa.String()),
    sa.Column("group_id", sa.Integer(), sa.ForeignKey("groups.id")),
)
snapshot.create_table(
    "groups",
    sa.Column("id", sa.Integer(), primary_key=True),
    sa.Column("name", sa.String()),
)
