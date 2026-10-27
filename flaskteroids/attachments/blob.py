import base64
import hashlib
import mimetypes
import secrets
import string
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import BinaryIO

from flask import current_app
from itsdangerous import BadSignature
from sqlalchemy import delete, insert, select

from flaskteroids.attachments.filenames import sanitize_filename
from flaskteroids.attachments.jobs import PurgeJob
from flaskteroids.attachments.operations import purge_blob, upload_blob
from flaskteroids.attachments.schema import attachments, blobs
from flaskteroids.attachments.services import (
    StorageError,
    UploadTooLarge,
    verify_checksum,
)
from flaskteroids.attachments.signatures import signed_token, verified_token
from flaskteroids.attachments.transactions import after_commit
from flaskteroids.db import session, transactional
from flaskteroids.exceptions import RecordNotFoundException


def storage():
    return current_app.extensions["flaskteroids.attachments"]


def detect_content_type(data, filename=None, declared_type=None):
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return "image/webp"
    if data.startswith(b"%PDF-"):
        return "application/pdf"
    stripped = data.lstrip().lower()
    if stripped.startswith((b"<!doctype html", b"<html", b"<script")):
        return "text/html"
    if stripped.startswith(b"<svg"):
        return "image/svg+xml"
    inferred = mimetypes.guess_type(filename or "")[0]
    if inferred:
        return inferred
    if declared_type and declared_type != "application/octet-stream":
        return declared_type
    try:
        if "\x00" not in data.decode("utf-8"):
            return "text/plain"
    except UnicodeDecodeError:
        pass
    return "application/octet-stream"


@dataclass(frozen=True)
class Upload:
    stream: BinaryIO
    filename: str
    content_type: str
    byte_size: int
    checksum: str

    @classmethod
    def read(cls, stream, *, filename, max_size=None, content_type=None, identify=True):
        if max_size is not None and (type(max_size) is not int or max_size < 1):
            raise StorageError("max_upload_size must be None or a positive integer")
        if not isinstance(filename, str):
            raise StorageError("Uploads require a filename")
        filename = sanitize_filename(filename)
        if len(filename) > 255:
            raise StorageError("Filename is too long")
        spool = tempfile.SpooledTemporaryFile(max_size=1024 * 1024, mode="w+b")
        checksum = hashlib.md5(usedforsecurity=False)
        size = 0
        sample = b""
        try:
            stream.seek(0)
            if not isinstance(stream.read(0), bytes):
                raise StorageError("Uploads must use a binary stream")
            while chunk := stream.read(64 * 1024):
                if not isinstance(chunk, bytes):
                    raise StorageError("Uploads must use a binary stream")
                size += len(chunk)
                if max_size is not None and size > max_size:
                    raise UploadTooLarge(
                        f"File exceeds the {max_size} byte upload limit"
                    )
                if len(sample) < 4096:
                    sample += chunk[: 4096 - len(sample)]
                spool.write(chunk)
                checksum.update(chunk)
            stream.seek(0)
            spool.seek(0)
            if identify or not content_type:
                content_type = detect_content_type(sample, filename, content_type)
            return cls(
                spool,
                filename,
                content_type,
                size,
                base64.b64encode(checksum.digest()).decode(),
            )
        except BaseException:
            spool.close()
            raise

    def close(self):
        self.stream.close()


@dataclass(frozen=True)
class Blob:
    id: int
    key: str
    filename: str
    content_type: str
    service_name: str
    byte_size: int
    checksum: str
    created_at: datetime

    @classmethod
    def find(cls, id):
        row = session.execute(select(blobs).where(blobs.c.id == id)).mappings().first()
        if row is None:
            raise RecordNotFoundException(f"Blob {id} was not found")
        return cls(**row)

    @classmethod
    def find_signed(cls, signed_id, *, purpose="blob_id"):
        try:
            return cls.find_signed_or_raise(signed_id, purpose=purpose)
        except BadSignature, RecordNotFoundException:
            return None

    @classmethod
    def find_signed_or_raise(cls, signed_id, *, purpose="blob_id"):
        payload = verified_token(purpose, signed_id)
        if type(payload.get("id")) is not int or not isinstance(
            payload.get("key"), str
        ):
            raise BadSignature("Invalid blob ID")
        blob = cls.find(payload["id"])
        if blob.key != payload["key"]:
            raise BadSignature("The blob ID has been invalidated")
        return blob

    @classmethod
    @transactional
    def create_and_upload(
        cls, *, io, filename, service_name=None, content_type=None, identify=True
    ):
        upload = Upload.read(
            io,
            filename=filename,
            content_type=content_type,
            identify=identify,
            max_size=current_app.config.attachments.max_upload_size,
        )
        try:
            blob = cls._create(upload, service_name or storage().service_name)
            upload_blob(blob, upload)
            return blob
        finally:
            upload.close()

    @classmethod
    @transactional
    def purge_unattached(cls, *, older_than=timedelta(days=2)):
        if not isinstance(older_than, timedelta) or older_than <= timedelta(0):
            raise ValueError("older_than must be a positive timedelta")
        cutoff = datetime.now(UTC) - older_than
        query = select(blobs).where(
            blobs.c.created_at < cutoff,
            ~select(attachments.c.id)
            .where(attachments.c.blob_id == blobs.c.id)
            .exists(),
        )
        pending = [cls(**row) for row in session.execute(query).mappings()]
        for blob in pending:
            blob.purge_later()
        return len(pending)

    @classmethod
    def _create(cls, upload, service_name):
        storage().service(service_name)
        key = "".join(
            secrets.choice(string.ascii_lowercase + string.digits) for _ in range(28)
        )
        values = {
            "key": key,
            "filename": upload.filename,
            "content_type": upload.content_type,
            "service_name": service_name,
            "byte_size": upload.byte_size,
            "checksum": upload.checksum,
            "created_at": datetime.now(UTC),
        }
        result = session.execute(insert(blobs).values(**values))
        return cls(id=result.inserted_primary_key[0], **values)

    @property
    def service(self):
        return storage().service(self.service_name)

    @property
    def attachments(self):
        return [
            Attachment(**row)
            for row in session.execute(
                select(attachments).where(attachments.c.blob_id == self.id)
            ).mappings()
        ]

    def signed_id(self, *, expires_in=None, purpose="blob_id"):
        return signed_token(purpose, {"id": self.id, "key": self.key}, expires_in)

    @property
    def attachable_sgid(self):
        return self.signed_id(purpose="rich_text_attachable")

    def serving_options(self, disposition="inline"):
        if disposition not in {"attachment", "inline"}:
            raise ValueError("Disposition must be attachment or inline")
        config = current_app.config.attachments
        content_type = self.content_type
        if content_type in config.content_types_to_serve_as_binary:
            content_type = "application/octet-stream"
            disposition = "attachment"
        elif content_type not in config.content_types_allowed_inline:
            disposition = "attachment"
        return {"content_type": content_type, "disposition": disposition}

    def url(self, *, expires_in=None, disposition="inline", filename=None):
        expires_in = (
            current_app.config.attachments.service_urls_expire_in
            if expires_in is None
            else expires_in
        )
        return self.service.url(
            self.key,
            expires_in=expires_in,
            filename=sanitize_filename(filename or self.filename),
            **self.serving_options(disposition),
        )

    def download(self, callback=None):
        return self.service.download(self.key, callback)

    @contextmanager
    def open(self, *, tmpdir=None):
        suffix = Path(self.filename).suffix
        with tempfile.NamedTemporaryFile(
            prefix=f"Attachments-{self.id}-", suffix=suffix, dir=tmpdir
        ) as stream:
            self.download(stream.write)
            verify_checksum(stream, self.checksum)
            yield stream

    @transactional
    def purge(self):
        return purge_blob(self.id, self.key, self.service_name)

    @transactional
    def purge_later(self):
        after_commit(
            session,
            lambda: PurgeJob().perform_later(self.id, self.key, self.service_name),
        )


@dataclass(frozen=True)
class Attachment:
    id: int
    name: str
    record_type: str
    record_id: int
    blob_id: int
    created_at: datetime
    _blob: Blob | None = field(default=None, compare=False, repr=False)

    @property
    def blob(self):
        return self._blob or Blob.find(self.blob_id)

    def __getattr__(self, name):
        return getattr(self.blob, name)

    @transactional
    def detach(self):
        session.execute(delete(attachments).where(attachments.c.id == self.id))

    @transactional
    def purge(self):
        blob = self.blob
        self.detach()
        return blob.purge()

    @transactional
    def purge_later(self):
        blob = self.blob
        self.detach()
        blob.purge_later()
