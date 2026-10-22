import sqlalchemy as sa

from flaskteroids.schema import Snapshot

snapshot = Snapshot()
metadata = snapshot.metadata
snapshot.create_table(
    "products",
    sa.Column("id", sa.Integer(), primary_key=True),
    sa.Column("name", sa.String()),
    sa.Column("quantity", sa.Integer()),
)
snapshot.create_table(
    "subscribers",
    sa.Column("id", sa.Integer(), primary_key=True),
    sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id")),
    sa.Column("email", sa.String()),
    sa.Column("password_digest", sa.String()),
)
for table in ("fish", "equipment"):
    snapshot.create_table(
        table,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id")),
        sa.Column("name", sa.String()),
    )
snapshot.create_table(
    "categories",
    sa.Column("id", sa.Integer(), primary_key=True),
    sa.Column("slug", sa.String()),
)
