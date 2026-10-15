import io
from pathlib import Path

import pytest
from werkzeug.datastructures import FileStorage

from flaskteroids.attachments import Blob, IntegrityError, StorageError
from flaskteroids.attachments.jobs import PurgeJob
from flaskteroids.db import session
from flaskteroids.model import RecordNotFoundException
from tests.attachments.app.models.document import Document

pytestmark = pytest.mark.usefixtures("app_ctx")


def test_attachment_is_saved_with_new_record(upload, storage):
    document = Document.new(title="Example", avatar=upload())
    assert document.avatar.attached()
    assert document.avatar.byte_size == 13
    assert document.save()
    blob = document.avatar.blob
    assert blob.filename == "avatar.png"
    assert blob.content_type == "image/png"
    assert not storage.service().exist(blob.key)
    assert Blob.find(blob.id).filename == "avatar.png"
    session.commit()
    assert storage.service().exist(blob.key)
    assert Document.find(document.id).avatar.download() == b"\x89PNG\r\n\x1a\nimage"
    with blob.open() as stream:
        assert stream.read() == blob.download()
        path = Path(stream.name)
        assert path.is_file()
    assert stream.closed
    assert not path.exists()


def test_attach_to_persisted_record_saves_immediately(upload):
    document = Document.create(title="Example")
    assert not document.avatar.attached()
    assert document.avatar.attach(upload()) is not None
    assert Document.find(document.id).avatar.attached()


def test_attach_does_not_save_other_pending_changes(upload):
    document = Document.create(title="Original")
    document.title = "Changed"
    document.avatar.attach(upload())
    assert Document.find(document.id) is document
    assert document.read_published_attribute("title") == "Original"
    assert document.avatar.attachment is None
    assert document.save()
    assert Document.find(document.id).avatar.attached()
    assert Document.find(document.id).title == "Changed"


def test_failed_validation_keeps_upload_for_retry(upload):
    document = Document.new(avatar=upload())
    assert document.save() is False
    assert document.avatar.attached()
    document.title = "Fixed"
    assert document.save()
    session.commit()
    assert document.avatar.download() == b"\x89PNG\r\n\x1a\nimage"


@pytest.mark.parametrize(
    "data, message",
    [
        (b"%PDF-1.7", "unsupported content type"),
        (b"\x89PNG\r\n\x1a\n" + b"x" * 256, "exceeds 256 bytes"),
    ],
)
def test_attachment_validations_do_not_save_record(upload, data, message):
    document = Document.new(title="Invalid", avatar=upload(data))
    assert document.save() is False
    assert any(message in error for error in document.errors.full_messages())
    assert Document.count() == 0


def test_global_upload_limit_is_enforced(app, upload):
    app.config.attachments.max_upload_size = 4
    with pytest.raises(StorageError, match="upload limit"):
        Document.new(title="Too big", files=[upload(b"12345")])


def test_multiple_attach_appends_and_assignment_replaces(upload, storage, app):
    document = Document.create(title="Example", files=[upload(b"first", "first.txt")])
    first = document.files.blobs[0]
    document.files.attach(upload(b"second", "second.txt"))
    assert [blob.filename for blob in document.files] == ["first.txt", "second.txt"]
    second = document.files.blobs[1]
    document.files = [second, second]
    assert document.save()
    session.commit()
    assert storage.service().exist(first.key)
    jobs = app.extensions["flaskteroids.jobs"].queue_adapter
    assert jobs.enqueued_jobs[0].job_class is PurgeJob
    jobs.perform_all()
    session.commit()
    assert not storage.service().exist(first.key)
    assert [blob.filename for blob in document.files] == ["second.txt"]


def test_multiple_pending_attachments_can_be_appended_before_save(upload):
    document = Document.new(title="Example", files=[upload(b"one", "one.txt")])
    document.files.attach(upload(b"two", "two.txt"))
    assert document.save()
    assert len(document.files) == 2


def test_replacement_is_rolled_back_without_deleting_old_blob(upload, storage, app):
    document = Document.create(title="Example", avatar=upload())
    original = document.avatar.blob
    session.commit()
    document.avatar.attach(upload(b"\x89PNG\r\n\x1a\nnew", "new.png"))
    replacement = document.avatar.blob
    session.rollback()
    assert Document.find(document.id).avatar.blob.id == original.id
    assert storage.service().exist(original.key)
    assert not storage.service().exist(replacement.key)
    assert not app.extensions["flaskteroids.jobs"].queue_adapter.enqueued_jobs
    with pytest.raises(RecordNotFoundException):
        Blob.find(replacement.id)


def test_model_upload_never_reaches_the_service_on_rollback(upload, storage, mocker):
    write = mocker.spy(storage.service(), "upload")
    document = Document.create(title="Example", avatar=upload())
    blob = document.avatar.blob
    write.assert_not_called()
    session.rollback()
    write.assert_not_called()
    assert not storage.service().exist(blob.key)
    assert Document.count() == 0


def test_nested_rollback_removes_only_nested_upload(upload, storage):
    outer = Document.create(title="Outer", avatar=upload())
    outer_blob = outer.avatar.blob
    nested = session.begin_nested()
    inner = Document.create(title="Inner", avatar=upload())
    inner_blob = inner.avatar.blob
    nested.rollback()
    assert not storage.service().exist(outer_blob.key)
    assert not storage.service().exist(inner_blob.key)
    session.commit()
    assert storage.service().exist(outer_blob.key)


def test_nested_commit_does_not_escape_outer_rollback(upload, storage):
    Document.create(title="Outer")
    with session.begin_nested():
        document = Document.create(title="Inner", avatar=upload())
        blob = document.avatar.blob
    session.rollback()
    assert not storage.service().exist(blob.key)
    assert Document.count() == 0


def test_detach_leaves_blob_and_file(upload, storage):
    document = Document.create(title="Example", avatar=upload())
    blob = document.avatar.blob
    session.commit()
    document.avatar.detach()
    session.commit()
    assert not document.avatar.attached()
    assert Blob.find(blob.id) == blob
    assert storage.service().exist(blob.key)


def test_purge_deletes_the_file_synchronously(upload, storage):
    document = Document.create(title="Example", avatar=upload())
    blob = document.avatar.blob
    session.commit()
    document.avatar.purge()
    assert not storage.service().exist(blob.key)
    session.commit()
    assert not document.avatar.attached()
    assert not storage.service().exist(blob.key)
    with pytest.raises(RecordNotFoundException):
        Blob.find(blob.id)


def test_shared_blob_is_not_purged_until_last_attachment_is_removed(
    upload, storage, app
):
    first = Document.create(title="First", avatar=upload())
    blob = first.avatar.blob
    session.commit()
    second = Document.create(title="Second", avatar=blob)
    first.avatar.purge_later()
    session.commit()
    app.extensions["flaskteroids.jobs"].queue_adapter.perform_all()
    session.commit()
    assert second.avatar.attached()
    assert storage.service().exist(blob.key)
    second.avatar.purge()
    session.commit()
    assert not storage.service().exist(blob.key)


def test_destroy_enqueues_purge_after_commit(upload, storage, app):
    document = Document.create(title="Example", avatar=upload())
    blob = document.avatar.blob
    document.destroy()
    adapter = app.extensions["flaskteroids.jobs"].queue_adapter
    assert not adapter.enqueued_jobs
    session.commit()
    assert len(adapter.enqueued_jobs) == 1
    adapter.perform_all()
    session.commit()
    assert not storage.service().exist(blob.key)


def test_destroy_rollback_preserves_attachment(upload, storage, app):
    document = Document.create(title="Example", avatar=upload())
    blob = document.avatar.blob
    session.commit()
    document.destroy()
    session.rollback()
    assert Document.find(document.id).avatar.attached()
    assert storage.service().exist(blob.key)
    assert not app.extensions["flaskteroids.jobs"].queue_adapter.enqueued_jobs


def test_blank_single_file_input_does_not_remove_existing_attachment(upload):
    document = Document.create(title="Example", avatar=upload())
    document.update(avatar=FileStorage(io.BytesIO(), filename=""))
    assert document.avatar.attached()
    assert document.update(avatar=None)
    assert not document.avatar.attached()


def test_signed_blob_id_can_retain_an_existing_attachment(upload):
    document = Document.create(title="Example", avatar=upload())
    blob = document.avatar.blob
    assert document.update(avatar=blob.signed_id())
    assert document.avatar.blob.id == blob.id


def test_programmatic_upload_and_integrity_check(storage):
    blob = Blob.create_and_upload(io=io.BytesIO(b"content"), filename="../report.txt")
    assert blob.filename == "report.txt"
    assert blob.download() == b"content"
    storage.service().path_for(blob.key).write_bytes(b"corrupt")
    assert blob.download() == b"corrupt"
    with pytest.raises(IntegrityError), blob.open():
        pass


def test_attachment_service_override_and_synchronous_purge(upload, storage, app):
    storage.configurations["archive"] = {"service": "Disk", "root": "archive-storage"}
    document = Document.create(
        title="Example", archive=upload(b"archive", "archive.txt")
    )
    blob = document.archive.blob
    assert blob.service_name == "archive"
    assert blob.service.root == app.project_root / "archive-storage"
    session.commit()
    document.archive.purge()
    assert not blob.service.exist(blob.key)
    session.commit()
    assert not blob.service.exist(blob.key)


def test_moving_a_blob_between_attachment_names_does_not_purge_it(upload, storage):
    storage.configurations["archive"] = {"service": "Disk", "root": "archive-storage"}
    document = Document.create(
        title="Example", archive=upload(b"archive", "archive.txt")
    )
    blob = document.archive.blob
    session.commit()
    assert document.update(archive=None, files=[blob])
    session.commit()
    assert document.files.blobs[0].download() == b"archive"


def test_dependent_none_preserves_blob_after_destroy(upload, app):
    document = Document.create(title="Example", backup=upload(b"backup", "backup.txt"))
    blob = document.backup.blob
    session.commit()
    document.destroy()
    session.commit()
    assert Blob.find(blob.id).download() == b"backup"
    assert not app.extensions["flaskteroids.jobs"].queue_adapter.enqueued_jobs


def test_attachment_metadata_is_available_in_after_commit_callbacks(upload):
    document = Document.create(title="Example", avatar=upload())
    session.commit()
    assert Document.committed_filenames[-1] == "avatar.png"
    assert Document.committed_contents[-1] == b"\x89PNG\r\n\x1a\nimage"
    assert document.update(title="Changed")
    session.commit()
    assert Document.committed_filenames[-1] == "avatar.png"


def test_keyword_attach_matches_rails_io_and_filename(upload):
    document = Document.create(title="Example")
    document.files.attach(io=io.BytesIO(b"report"), filename="report.txt")
    session.commit()
    assert document.files.blobs[0].download() == b"report"
    document.avatar.attach(io=upload().stream, filename="avatar.png")
    assert document.avatar.attached()


def test_nested_purge_is_not_enqueued_until_outer_commit(upload, app):
    document = Document.create(title="Example", avatar=upload())
    session.commit()
    with session.begin_nested():
        document.avatar.purge_later()
    jobs = app.extensions["flaskteroids.jobs"].queue_adapter
    assert not jobs.enqueued_jobs
    session.rollback()
    assert document.avatar.attached()
    assert not jobs.enqueued_jobs


def test_eager_purge_jobs_can_run_after_commit(upload, storage, app):
    document = Document.create(title="Example", avatar=upload())
    blob = document.avatar.blob
    session.commit()
    jobs = app.extensions["flaskteroids.jobs"].queue_adapter
    jobs.performing_enqueued_jobs = True
    document.avatar.purge_later()
    session.commit()
    session.commit()
    assert not storage.service().exist(blob.key)


def test_purge_job_is_idempotent_and_cleans_up_after_metadata_was_deleted(storage):
    blob = Blob.create_and_upload(io=io.BytesIO(b"content"), filename="report.txt")
    blob.purge_later()
    session.commit()
    job = PurgeJob()
    job.perform(blob.id, blob.key, blob.service_name)
    session.commit()
    job.perform(blob.id, blob.key, blob.service_name)
    assert not storage.service().exist(blob.key)
