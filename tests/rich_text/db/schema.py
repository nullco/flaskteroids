import sqlalchemy as sa

from flaskteroids.rich_text.schema import rich_texts

metadata = sa.MetaData()
for name in ("documents", "notes"):
    sa.Table(
        name,
        metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("title", sa.String),
        sa.Column("created_at", sa.DateTime),
        sa.Column("updated_at", sa.DateTime),
    )
metadata.tables["notes"].append_column(
    sa.Column("document_id", sa.Integer, sa.ForeignKey("documents.id"))
)
rich_texts.to_metadata(metadata)
