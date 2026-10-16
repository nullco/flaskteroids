import pytest
from flask import Response, stream_with_context
from sqlalchemy import MetaData, Table
from sqlalchemy.orm import registry

from flaskteroids.attachments import Blob
from flaskteroids.db import session
from flaskteroids.exceptions import RecordNotFoundException
from flaskteroids.testing import get
from flaskteroids.testing.context import activate_test_context, current_response
from flaskteroids.testing.database import transactional_test
from tests.attachments.app.models.document import Document


@pytest.mark.parametrize("operation", ["replace", "destroy"])
def test_dependent_purge_commits_metadata_during_app_teardown(
    app, storage, upload, operation
):
    storage.configurations["archive"] = {"service": "Disk", "root": "archive"}
    with app.app_context():
        document = Document.create(title="Example", archive=upload(b"old", "old.txt"))
        document_id = document.id
        blob = document.archive.blob
        service = blob.service
    assert service.exist(blob.key)

    with app.app_context():
        document = Document.find(document_id)
        if operation == "replace":
            assert document.update(archive=upload(b"new", "new.txt"))
        else:
            assert document.destroy()

    assert not service.exist(blob.key)
    with app.app_context():
        with pytest.raises(RecordNotFoundException):
            Blob.find(blob.id)
        if operation == "replace":
            assert Document.find(document_id).archive.download() == b"new"


def test_dependent_purge_preserves_a_shared_blob_during_app_teardown(
    app, storage, upload
):
    storage.configurations["archive"] = {"service": "Disk", "root": "archive"}
    with app.app_context():
        original = Document.create(
            title="Original", archive=upload(b"shared", "shared.txt")
        )
        original_id = original.id
        blob = original.archive.blob
        shared = Document.create(title="Shared", files=[blob])
        shared_id = shared.id
    with app.app_context():
        assert Document.find(original_id).destroy()
    with app.app_context():
        assert Document.find(shared_id).files.blobs[0].download() == b"shared"
        assert Blob.find(blob.id).key == blob.key


@pytest.mark.parametrize(
    "operation", ["clear", "detach", "attachment_detach", "destroy"]
)
def test_pending_blob_reuse_survives_removing_original_attachment(
    app, storage, upload, mocker, operation
):
    with app.app_context(), Document.transaction():
        write = mocker.spy(storage.service(), "upload")
        original = Document.create(title="Original", avatar=upload())
        blob = original.avatar.blob
        shared = Document.create(title="Shared", avatar=blob)
        shared_id = shared.id
        if operation == "clear":
            assert original.update(avatar=None)
        elif operation == "detach":
            original.avatar.detach()
        elif operation == "attachment_detach":
            original.avatar.attachment.detach()
        else:
            assert original.destroy()
        write.assert_not_called()
    write.assert_called_once()
    assert write.call_args.args[1].closed
    with app.app_context():
        assert Document.find(shared_id).avatar.download() == b"\x89PNG\r\n\x1a\nimage"


def test_pending_blob_can_move_between_attachment_names(app, upload):
    with app.app_context():
        document = Document.create(title="Example", avatar=upload())
        blob = document.avatar.blob
        assert document.update(avatar=None, files=[blob])
        document_id = document.id
    with app.app_context():
        document = Document.find(document_id)
        assert not document.avatar.attached()
        assert document.files.blobs[0].download() == b"\x89PNG\r\n\x1a\nimage"


def test_nested_removal_of_shared_pending_blob_preserves_its_upload(app, upload):
    with app.app_context(), Document.transaction():
        original = Document.create(title="Original", avatar=upload())
        with session.begin_nested():
            shared = Document.create(title="Shared", avatar=original.avatar.blob)
            assert original.update(avatar=None)
        shared_id = shared.id
    with app.app_context():
        assert Document.find(shared_id).avatar.download() == b"\x89PNG\r\n\x1a\nimage"


def test_clearing_pending_collection_cancels_unshared_uploads(
    app, storage, upload, mocker
):
    with app.app_context(), Document.transaction():
        write = mocker.spy(storage.service(), "upload")
        document = Document.create(title="Example", files=[upload(b"file", "file.txt")])
        assert document.update(files=[])
    write.assert_not_called()


def test_rolled_back_shared_attachment_does_not_keep_a_cancelled_upload(
    app, storage, upload, mocker
):
    with app.app_context(), Document.transaction():
        write = mocker.spy(storage.service(), "upload")
        original = Document.create(title="Original", avatar=upload())
        nested = session.begin_nested()
        Document.create(title="Shared", avatar=original.avatar.blob)
        nested.rollback()
        original.avatar.detach()
    write.assert_not_called()
    with app.app_context():
        assert Document.count() == 1
        assert not Document.first().avatar.attached()


def test_requests_do_not_commit_an_explicit_ambient_transaction(
    app, client, storage, upload, mocker
):
    app.add_url_rule("/request-count", view_func=lambda: {"count": Document.count()})
    with app.app_context(), Document.transaction():
        write = mocker.spy(storage.service(), "upload")
        Document.create(title="Setup", avatar=upload())
        assert client.get("/request-count").json == {"count": 1}
        write.assert_not_called()
    write.assert_called_once()


def test_transactional_test_restores_the_wsgi_application(app):
    original = app.wsgi_app
    with transactional_test(app):
        assert app.wsgi_app is not original
    assert app.wsgi_app is original


def test_streamed_test_requests_keep_their_isolated_context(
    app, client, storage, upload, mocker
):
    def streamed_request():
        @stream_with_context
        def body():
            yield f"{Document.count()}\n"
            Document.create(title="Streamed", avatar=upload())
            yield "done\n"

        return Response(body(), mimetype="text/plain")

    app.add_url_rule("/request-stream", view_func=streamed_request)
    with transactional_test(app), app.app_context(), Document.transaction():
        write = mocker.spy(storage.service(), "upload")
        Document.create(title="Setup", avatar=upload())
        response = client.get("/request-stream", buffered=False)
        assert response.data == b"1\ndone\n"
        response.close()
        write.assert_called_once()
        assert Document.count() == 2


def test_request_helper_does_not_commit_ambient_uploads(
    app, client, storage, upload, mocker
):
    def create_document():
        document = Document.create(title="Request")
        return {"id": document.id}

    app.add_url_rule(
        "/request-write", endpoint="request_write", view_func=create_document
    )
    with (
        transactional_test(app),
        app.app_context(),
        activate_test_context(client),
        Document.transaction(),
    ):
        write = mocker.spy(storage.service(), "upload")
        setup_document = Document.create(title="Setup", avatar=upload())
        get("/request-write")
        assert current_response().status_code == 200
        write.assert_not_called()
        assert Document.count() == 2
        assert setup_document.avatar.attached()


def test_request_preserves_unflushed_ambient_session_changes(app, client):
    app.add_url_rule("/request-read", view_func=lambda: {"count": Document.count()})
    with transactional_test(app), app.app_context(), activate_test_context(client):
        document = Document.create(title="Setup")

        class Record:
            pass

        table = Table("documents", MetaData(), autoload_with=session.connection())
        registry().map_imperatively(Record, table)
        record = session.get(Record, document.id)
        record.title = "Pending"
        get("/request-read")
        assert current_response().json == {"count": 1}
        assert record.title == "Pending"
        assert session.is_modified(record)


@pytest.mark.parametrize("propagate", [False, True])
def test_failed_request_rolls_back_only_request_work(
    app, client, storage, upload, mocker, propagate
):
    app.config["PROPAGATE_EXCEPTIONS"] = propagate

    def fail_after_write():
        with Document.transaction():
            Document.create(title="Failed request", avatar=upload())
            raise RuntimeError("Request failed")

    app.add_url_rule("/request-failure", view_func=fail_after_write)
    with transactional_test(app), app.app_context(), activate_test_context(client):
        Document.create(title="Setup")
        write = mocker.spy(storage.service(), "upload")
        if propagate:
            with pytest.raises(RuntimeError, match="Request failed"):
                get("/request-failure")
        else:
            get("/request-failure")
            assert current_response().status_code == 500
        write.assert_not_called()
        assert Document.count() == 1
        assert Document.first().title == "Setup"


def test_eager_purge_job_commits_metadata_during_app_teardown(app, storage, upload):
    with app.app_context():
        document = Document.create(title="Example", avatar=upload())
        document_id = document.id
        blob = document.avatar.blob
        service = blob.service
    jobs = app.extensions["flaskteroids.jobs"].queue_adapter
    jobs.performing_enqueued_jobs = True
    with app.app_context():
        Document.find(document_id).destroy()
    assert not service.exist(blob.key)
    with app.app_context(), pytest.raises(RecordNotFoundException):
        Blob.find(blob.id)


def test_dependent_purge_metadata_commits_before_storage_deletion(
    app, storage, upload, mocker
):
    storage.configurations["archive"] = {"service": "Disk", "root": "archive"}
    with app.app_context():
        document = Document.create(title="Example", archive=upload(b"old", "old.txt"))
        document_id = document.id
        blob = document.archive.blob
        service = blob.service
    mocker.patch.object(service, "delete", side_effect=OSError("Storage unavailable"))
    with pytest.raises(OSError, match="Storage unavailable"), app.app_context():
        Document.find(document_id).destroy()
    with app.app_context(), pytest.raises(RecordNotFoundException):
        Blob.find(blob.id)
    assert service.exist(blob.key)
