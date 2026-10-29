"""Public contract and shared utilities for attachment storage providers."""

import base64
import hashlib
import hmac
import io
import re
import unicodedata
from abc import ABC, abstractmethod
from collections.abc import Callable
from contextlib import closing
from pathlib import Path
from typing import Any, BinaryIO, Protocol, Self
from urllib.parse import quote

from werkzeug.http import dump_options_header


class StorageError(RuntimeError):
    pass


class IntegrityError(StorageError):
    pass


class UploadTooLarge(StorageError):
    pass


class StorageStream(Protocol):
    """A readable binary stream. The caller owns and closes it."""

    def read(self, size: int = -1) -> bytes: ...

    def close(self) -> None: ...


class StorageService(ABC):
    """Per-application storage provider, discovered via flaskteroids.storage."""

    def __init__(self, *, public: bool = False) -> None:
        self.public = public
        self.name: str | None = None

    @classmethod
    def from_config(cls, project_root: Path, **options: Any) -> Self:
        """Construct from resolved storage.yml options, without global state."""
        return cls(**options)

    @abstractmethod
    def upload(
        self,
        key: str,
        data: bytes | BinaryIO,
        *,
        checksum: str | None = None,
        content_type: str | None = None,
        filename: str | None = None,
        disposition: str | None = None,
    ) -> None:
        """Persist bytes or a seekable binary stream; reject checksum mismatches."""

    @abstractmethod
    def open(
        self, key: str, *, start: int | None = None, end: int | None = None
    ) -> StorageStream:
        """Open an inclusive byte range; raise FileNotFoundError for missing keys."""

    def download(
        self, key: str, callback: Callable[[bytes], object] | None = None
    ) -> bytes | None:
        with closing(self.open(key)) as stream:
            if callback is None:
                return stream.read()
            while chunk := stream.read(64 * 1024):
                callback(chunk)
        return None

    @abstractmethod
    def delete(self, key: str) -> None:
        """Delete a key. Deleting a missing key succeeds."""

    @abstractmethod
    def exist(self, key: str) -> bool:
        """Return False only for missing files; propagate permission failures."""

    @abstractmethod
    def url(
        self,
        key: str,
        *,
        expires_in: int,
        filename: str,
        content_type: str,
        disposition: str,
    ) -> str:
        """Return an absolute public or expiring URL with safe response headers."""

    def local_path(self, key: str) -> Path | None:
        """Optional local-file delivery optimization; remote providers return None."""
        return None


def validate_range(start: int | None, end: int | None) -> None:
    if (start is not None and start < 0) or (end is not None and end < (start or 0)):
        raise StorageError("Invalid storage byte range")


def verify_checksum(data: bytes | BinaryIO, checksum: str) -> None:
    stream = io.BytesIO(data) if isinstance(data, bytes) else data
    digest = hashlib.md5(usedforsecurity=False)
    stream.seek(0)
    while chunk := stream.read(64 * 1024):
        digest.update(chunk)
    stream.seek(0)
    actual = base64.b64encode(digest.digest()).decode()
    if not hmac.compare_digest(actual, checksum):
        raise IntegrityError("The uploaded file does not match its checksum")


def validate_key(key: object) -> None:
    if not isinstance(key, str) or not re.fullmatch(r"[a-z0-9]{28,64}", key):
        raise StorageError("Invalid storage key")


def sanitize_filename(filename: str) -> str:
    filename = filename.replace("\\", "/").split("/")[-1].strip()
    unsafe = '%$|:;/<>?*"\u202e'
    return (
        "".join(
            "-"
            if character in unsafe or ord(character) < 32 or ord(character) == 127
            else character
            for character in filename
        )
        or "file"
    )


def content_disposition(filename: str, disposition: str) -> str:
    filename = sanitize_filename(filename)
    try:
        filename.encode("ascii")
        options = {"filename": filename}
    except UnicodeEncodeError:
        fallback = (
            unicodedata.normalize("NFKD", filename).encode("ascii", "ignore").decode()
            or "file"
        )
        options = {
            "filename": fallback,
            "filename*": "UTF-8''" + quote(filename, safe=""),
        }
    return dump_options_header(disposition, options)
