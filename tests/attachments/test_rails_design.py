import io
from pathlib import Path

import pytest
from itsdangerous import BadSignature

from flaskteroids.attachments import Blob
from flaskteroids.attachments.services import S3Service
from flaskteroids.db import session
from tests.attachments.app.models.document import Document

pytestmark = pytest.mark.usefixtures("app_ctx")
PNG = b"\x89PNG\r\n\x1a\n"


@pytest.mark.usefixtures("pending_transaction")
def test_upload_runs_once_after_commit_and_before_model_callbacks(
    upload, storage, mocker
):
    write = mocker.spy(storage.service(), "upload")
    document = Document.create(title="Example", avatar=upload())
    blob = document.avatar.blob
    assert document.save()
    assert document.avatar.blob.key == blob.key
    assert Document.saved_blob_ids[-1] == blob.id
    write.assert_not_called()
    session.commit()
    write.assert_called_once()
    assert Document.committed_contents[-1] == PNG + b"image"
    assert write.call_args.args[1].closed


def test_nested_commit_delays_upload_and_callbacks_until_outer_commit(
    upload, storage, mocker
):
    write = mocker.spy(storage.service(), "upload")
    Document.create(title="Outer")
    before = len(Document.committed_contents)
    with session.begin_nested():
        document = Document.create(title="Inner", avatar=upload())
        blob = document.avatar.blob
    write.assert_not_called()
    assert len(Document.committed_contents) == before
    session.commit()
    write.assert_called_once()
    assert storage.service().exist(blob.key)
    assert len(Document.committed_contents) == before + 1


@pytest.mark.usefixtures("pending_transaction")
def test_nested_replacement_commits_only_the_latest_single_upload(
    upload, storage, mocker
):
    write = mocker.spy(storage.service(), "upload")
    document = Document.create(title="Example", avatar=upload(PNG + b"first"))
    original = document.avatar.blob
    with session.begin_nested():
        document.avatar.attach(upload(PNG + b"second"))
    replacement = document.avatar.blob
    write.assert_not_called()
    session.commit()
    write.assert_called_once()
    assert not storage.service().exist(original.key)
    assert storage.service().exist(replacement.key)
    assert Document.committed_contents[-1] == PNG + b"second"


@pytest.mark.usefixtures("pending_transaction")
def test_nested_replacement_rollback_preserves_outer_upload_and_callback_snapshot(
    upload, storage, mocker
):
    write = mocker.spy(storage.service(), "upload")
    document = Document.create(title="Example", avatar=upload(PNG + b"first"))
    original = document.avatar.blob
    nested = session.begin_nested()
    document.avatar.attach(upload(PNG + b"second"))
    replacement = document.avatar.blob
    nested.rollback()
    session.commit()
    write.assert_called_once()
    assert storage.service().exist(original.key)
    assert not storage.service().exist(replacement.key)
    assert Document.committed_contents[-1] == PNG + b"first"


@pytest.mark.usefixtures("pending_transaction")
def test_retaining_pending_blob_preserves_its_upload(upload, storage, mocker):
    write = mocker.spy(storage.service(), "upload")
    document = Document.create(title="Example", avatar=upload())
    blob = document.avatar.blob
    assert document.update(avatar=blob.signed_id())
    session.commit()
    write.assert_called_once()
    assert document.avatar.download() == PNG + b"image"


@pytest.mark.usefixtures("pending_transaction")
def test_clearing_pending_single_attachment_cancels_the_upload(upload, storage, mocker):
    write = mocker.spy(storage.service(), "upload")
    document = Document.create(title="Example", avatar=upload())
    blob = document.avatar.blob
    document.update(avatar=None)
    session.commit()
    write.assert_not_called()
    assert not document.avatar.attached()
    assert not storage.service().exist(blob.key)


@pytest.mark.usefixtures("pending_transaction")
def test_destroy_before_commit_cancels_all_pending_uploads(upload, storage, mocker):
    write = mocker.spy(storage.service(), "upload")
    document = Document.create(
        title="Example", avatar=upload(), files=[upload(b"file", "file.txt")]
    )
    document.destroy()
    session.commit()
    write.assert_not_called()
    assert Document.count() == 0


@pytest.mark.usefixtures("pending_transaction")
def test_multiple_uploads_survive_append_operations_in_one_transaction(
    upload, storage, mocker
):
    write = mocker.spy(storage.service(), "upload")
    document = Document.create(title="Example", files=[upload(b"one", "one.txt")])
    document.files.attach(upload(b"two", "two.txt"))
    write.assert_not_called()
    session.commit()
    assert write.call_count == 2
    assert [attachment.download() for attachment in document.files] == [b"one", b"two"]


def test_purge_later_rollback_keeps_metadata_and_existing_file(upload, app, storage):
    document = Document.create(title="Example", avatar=upload())
    blob = document.avatar.blob
    session.commit()
    session.begin()
    document.avatar.purge_later()
    session.rollback()
    assert document.avatar.attached()
    assert storage.service().exist(blob.key)
    assert not app.extensions["flaskteroids.jobs"].queue_adapter.enqueued_jobs


def test_file_and_path_attachables_can_be_closed_before_commit(tmp_path):
    path = tmp_path / "report.txt"
    path.write_bytes(b"report")
    document = Document.create(title="Example")
    document.files.attach(path)
    with path.open("rb") as stream:
        document.files.attach(stream)
    session.commit()
    assert [attachment.download() for attachment in document.files] == [
        b"report",
        b"report",
    ]


def test_large_uploads_use_streams_and_default_to_unlimited_size(app, storage, mocker):
    assert app.config.attachments.max_upload_size is None
    write = mocker.spy(storage.service(), "upload")
    data = b"x" * (11 * 1024 * 1024)
    document = Document.create(
        title="Large", files=[{"io": io.BytesIO(data), "filename": "large.txt"}]
    )
    session.commit()
    stream = write.call_args.args[1]
    assert not isinstance(stream, bytes)
    assert stream.closed
    assert document.files.blobs[0].byte_size == len(data)
    assert document.files.blobs[0].download() == data


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


@pytest.mark.parametrize("operation", ["detach", "purge", "purge_later"])
@pytest.mark.usefixtures("pending_transaction")
def test_explicit_removal_before_commit_cancels_pending_uploads(
    operation, upload, storage, mocker
):
    write = mocker.spy(storage.service(), "upload")
    document = Document.create(title="Example", avatar=upload())
    blob = document.avatar.blob
    getattr(document.avatar, operation)()
    session.commit()
    write.assert_not_called()
    assert not document.avatar.attached()
    assert not storage.service().exist(blob.key)


def test_outer_rollback_discards_committed_savepoint_uploads_and_purge_jobs(
    upload, storage, app, mocker
):
    document = Document.create(title="Example", avatar=upload())
    original = document.avatar.blob
    session.commit()
    write = mocker.spy(storage.service(), "upload")
    with session.begin_nested():
        document.avatar.attach(upload(PNG + b"replacement"))
    replacement = document.avatar.blob
    session.rollback()
    write.assert_not_called()
    assert document.avatar.blob.key == original.key
    assert storage.service().exist(original.key)
    assert not storage.service().exist(replacement.key)
    assert not app.extensions["flaskteroids.jobs"].queue_adapter.enqueued_jobs


def test_download_and_open_stream_file_contents_in_chunks():
    data = b"file data" * 20000
    blob = Blob.create_and_upload(io=io.BytesIO(data), filename="report.txt")
    chunks = []
    assert blob.download(chunks.append) is None
    assert b"".join(chunks) == data
    assert len(chunks) > 1
    with blob.open() as stream:
        assert stream.read() == data


def test_s3_upload_uses_safe_headers_for_public_objects(storage, mocker):
    client = mocker.Mock()
    mocker.patch.object(
        storage,
        "service",
        return_value=S3Service(bucket="uploads", client=client, public=True),
    )
    Blob.create_and_upload(io=io.BytesIO(b"<html>unsafe</html>"), filename="page.html")
    options = client.put_object.call_args.kwargs
    assert options["ContentType"] == "application/octet-stream"
    assert options["ContentDisposition"].startswith("attachment;")
    assert options["ACL"] == "public-read"


def test_s3_upload_retains_unicode_filenames_in_rfc5987_headers(storage, mocker):
    client = mocker.Mock()
    mocker.patch.object(
        storage, "service", return_value=S3Service(bucket="uploads", client=client)
    )
    blob = Blob.create_and_upload(io=io.BytesIO(b"report"), filename="../résumé.txt")
    assert blob.filename == "résumé.txt"
    disposition = client.put_object.call_args.kwargs["ContentDisposition"]
    assert "filename=resume.txt" in disposition
    assert "filename*=UTF-8''r%C3%A9sum%C3%A9.txt" in disposition


def test_find_signed_returns_none_and_raising_lookup_rejects_invalid_tokens():
    assert Blob.find_signed("invalid") is None
    with pytest.raises(BadSignature):
        Blob.find_signed_or_raise("invalid")
    blob = Blob.create_and_upload(io=io.BytesIO(b"report"), filename="report.txt")
    found = Blob.find_signed(blob.signed_id())
    assert found.id == blob.id
    assert found.key == blob.key
    assert Blob.find_signed(blob.signed_id(purpose="other")) is None


def test_attachments_report_blank_state_and_delegate_blob_attributes(upload):
    document = Document.new(title="Example")
    assert document.avatar.blank()
    assert not document.avatar
    document.avatar.attach(upload())
    assert not document.avatar.blank()
    assert document.save()
    session.commit()
    attachment = document.avatar.attachment
    assert attachment.filename == "avatar.png"
    assert attachment.download() == PNG + b"image"
