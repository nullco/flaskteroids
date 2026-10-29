import io
from pathlib import Path

import pytest
from itsdangerous import BadSignature

from flaskteroids.attachments import Blob

pytestmark = pytest.mark.usefixtures("app_ctx")
PNG = b"\x89PNG\r\n\x1a\n"


def test_explicit_content_type_can_skip_identification():
    blob = Blob.create_and_upload(
        io=io.BytesIO(PNG),
        filename="report.txt",
        content_type="application/pdf",
        identify=False,
    )
    assert blob.content_type == "application/pdf"
    identified = Blob.create_and_upload(
        io=io.BytesIO(PNG),
        filename="report.txt",
        content_type="application/pdf",
    )
    assert identified.content_type == "image/png"


def test_open_yields_a_checksum_verified_temporary_file(tmp_path):
    blob = Blob.create_and_upload(io=io.BytesIO(b"report"), filename="report.txt")
    with blob.open(tmpdir=tmp_path) as stream:
        path = Path(stream.name)
        assert path.parent == tmp_path
        assert path.suffix == ".txt"
        assert stream.read() == b"report"
    assert not path.exists()


def test_download_and_open_stream_file_contents_in_chunks():
    data = b"file data" * 20000
    blob = Blob.create_and_upload(io=io.BytesIO(data), filename="report.txt")
    chunks = []
    assert blob.download(chunks.append) is None
    assert b"".join(chunks) == data
    assert len(chunks) > 1
    with blob.open() as stream:
        assert stream.read() == data


def test_upload_passes_safe_headers_to_storage(remote_service):
    Blob.create_and_upload(
        io=io.BytesIO(b"<html>unsafe</html>"),
        filename="page.html",
        service_name="remote",
    )
    options = remote_service.uploads[0]
    assert options["content_type"] == "application/octet-stream"
    assert options["disposition"] == "attachment"


def test_upload_passes_sanitized_unicode_filenames_to_storage(remote_service):
    blob = Blob.create_and_upload(
        io=io.BytesIO(b"report"), filename="../résumé.txt", service_name="remote"
    )
    assert blob.filename == "résumé.txt"
    assert remote_service.uploads[0]["filename"] == "résumé.txt"


def test_find_signed_returns_none_and_raising_lookup_rejects_invalid_tokens():
    assert Blob.find_signed("invalid") is None
    with pytest.raises(BadSignature):
        Blob.find_signed_or_raise("invalid")
    blob = Blob.create_and_upload(io=io.BytesIO(b"report"), filename="report.txt")
    found = Blob.find_signed(blob.signed_id())
    assert found.id == blob.id
    assert found.key == blob.key
    assert Blob.find_signed(blob.signed_id(purpose="other")) is None
