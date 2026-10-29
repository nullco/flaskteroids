"""Reusable pytest contract for storage providers.

Subclass StorageServiceContract and supply a fresh storage_service fixture.
The fixture must support URL generation (including a request context for Disk).
No network or cloud credentials are required by the contract itself.
"""

import base64
import hashlib
import io
from contextlib import closing
from urllib.parse import urlsplit

import pytest

from flaskteroids.storage import IntegrityError, StorageError

KEY = "a" * 28
DATA = b"storage contract data"
CHECKSUM = base64.b64encode(hashlib.md5(DATA, usedforsecurity=False).digest()).decode()


class StorageServiceContract:
    def test_upload_download_and_idempotent_delete(self, storage_service):
        assert not storage_service.exist(KEY)
        storage_service.upload(KEY, DATA, checksum=CHECKSUM, content_type="text/plain")
        assert storage_service.exist(KEY)
        assert storage_service.download(KEY) == DATA
        storage_service.delete(KEY)
        storage_service.delete(KEY)
        assert not storage_service.exist(KEY)

    def test_upload_accepts_seekable_binary_streams(self, storage_service):
        with io.BytesIO(DATA) as stream:
            storage_service.upload(KEY, stream, checksum=CHECKSUM)
        assert storage_service.download(KEY) == DATA

    def test_upload_rejects_checksum_mismatches(self, storage_service):
        with pytest.raises(IntegrityError):
            storage_service.upload(KEY, DATA, checksum="invalid")
        assert not storage_service.exist(KEY)

    @pytest.mark.parametrize(
        "start, end", [(None, None), (0, 3), (4, None), (None, 3), (0, 0)]
    )
    def test_open_reads_inclusive_byte_ranges(self, storage_service, start, end):
        storage_service.upload(KEY, DATA)
        with closing(storage_service.open(KEY, start=start, end=end)) as stream:
            assert stream.read() == DATA[start or 0 : None if end is None else end + 1]

    @pytest.mark.parametrize("start, end", [(-1, None), (2, 1), (None, -1)])
    def test_open_rejects_invalid_ranges(self, storage_service, start, end):
        storage_service.upload(KEY, DATA)
        with pytest.raises(StorageError):
            storage_service.open(KEY, start=start, end=end)

    def test_open_reports_missing_files(self, storage_service):
        with pytest.raises(FileNotFoundError):
            storage_service.open(KEY)

    def test_download_delivers_bounded_chunks(self, storage_service):
        data = DATA * 10000
        storage_service.upload(KEY, data)
        chunks = []
        assert storage_service.download(KEY, chunks.append) is None
        assert b"".join(chunks) == data
        assert all(0 < len(chunk) <= 64 * 1024 for chunk in chunks)

    @pytest.mark.parametrize("operation", ["open", "download", "delete", "exist"])
    @pytest.mark.parametrize(
        "key", ["../escape", "/etc/passwd", "short", "a" * 27 + "/"]
    )
    def test_operations_reject_unsafe_keys(self, storage_service, operation, key):
        with pytest.raises(StorageError):
            getattr(storage_service, operation)(key)

    def test_upload_rejects_unsafe_keys(self, storage_service):
        with pytest.raises(StorageError):
            storage_service.upload("../escape", DATA)

    def test_url_is_absolute_and_rejects_unsafe_keys(self, storage_service):
        options = {
            "expires_in": 300,
            "filename": "report.txt",
            "content_type": "text/plain",
            "disposition": "attachment",
        }
        url = urlsplit(storage_service.url(KEY, **options))
        assert url.scheme in {"http", "https"}
        assert url.netloc
        with pytest.raises(StorageError):
            storage_service.url("../escape", **options)
