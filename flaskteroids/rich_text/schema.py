from sqlalchemy import Column, DateTime, Index, Integer, MetaData, String, Table, Text

metadata = MetaData()
rich_texts = Table(
    "rich_texts",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("name", String(255), nullable=False),
    Column("body", Text, nullable=False),
    Column("record_type", String(255), nullable=False),
    Column("record_id", Integer, nullable=False),
    Column("created_at", DateTime, nullable=False),
    Column("updated_at", DateTime, nullable=False),
    Index(
        "index_rich_texts_uniqueness",
        "record_type",
        "record_id",
        "name",
        unique=True,
    ),
)
