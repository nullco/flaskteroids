from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    String,
    Table,
)

metadata = MetaData()

blobs = Table(
    "attachment_blobs",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("key", String(255), nullable=False),
    Column("filename", String(255), nullable=False),
    Column("content_type", String(255), nullable=False),
    Column("service_name", String(255), nullable=False),
    Column("byte_size", BigInteger, nullable=False),
    Column("checksum", String(255), nullable=False),
    Column("created_at", DateTime, nullable=False),
    Index("index_attachment_blobs_on_key", "key", unique=True),
    sqlite_autoincrement=True,
)

attachments = Table(
    "record_attachments",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("name", String(255), nullable=False),
    Column("record_type", String(255), nullable=False),
    Column("record_id", Integer, nullable=False),
    Column("blob_id", Integer, ForeignKey(blobs.c.id), nullable=False),
    Column("created_at", DateTime, nullable=False),
    Index(
        "index_record_attachments_uniqueness",
        "record_type",
        "record_id",
        "name",
        "blob_id",
        unique=True,
    ),
    sqlite_autoincrement=True,
)
