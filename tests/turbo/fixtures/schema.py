import sqlalchemy as sa

from flaskteroids.schema import Snapshot

snapshot = Snapshot()
metadata = snapshot.metadata
snapshot.create_table(
    "memberships",
    sa.Column("account_id", sa.Integer(), primary_key=True),
    sa.Column("member_id", sa.Integer(), primary_key=True),
)
