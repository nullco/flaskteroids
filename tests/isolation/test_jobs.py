from io import BytesIO

import pytest

from flaskteroids.attachments import Blob
from flaskteroids.attachments.jobs import PurgeJob
from flaskteroids.db import session
from flaskteroids.exceptions import ProgrammerError, RecordNotFoundException
from flaskteroids.jobs.adapters import CeleryQueueAdapter
from flaskteroids.jobs.job import Job
from flaskteroids.mailer import MessageDeliveryJob
from tests.isolation.jobs.record import RecordJob
from tests.isolation.mailers.notice import NoticeMailer
from tests.isolation.models.records import Author


@pytest.mark.parametrize("order", [("a", "b"), ("b", "a")])
def test_enqueue_and_drain_use_the_owning_app(make_app, order):
    apps = {name: make_app(name) for name in order}
    for name in ("a", "b", "a"):
        with apps[name].app_context():
            RecordJob().perform_later(name)
    a = apps["a"].extensions["flaskteroids.jobs"].queue_adapter
    b = apps["b"].extensions["flaskteroids.jobs"].queue_adapter
    assert len(a.enqueued_jobs) == 2
    assert len(b.enqueued_jobs) == 1
    with apps["b"].app_context():
        a.perform_all()
    b.perform_all()
    assert apps["a"].config["EVENTS"] == [("job", "a", "a")] * 2
    assert apps["b"].config["EVENTS"] == [("job", "b", "b")]


def test_job_registration_is_idempotent_and_unambiguous(make_app):
    app = make_app("a")
    jobs = app.extensions["flaskteroids.jobs"]
    name = "tests.isolation.jobs.RecordJob"
    jobs.register_job(name, RecordJob)
    jobs.register_job(name, RecordJob)
    with pytest.raises(ProgrammerError, match="name|registered"):
        jobs.register_job("other", RecordJob)
    with pytest.raises(ProgrammerError, match="name|registered"):
        jobs.register_job(name, Job)
    with app.app_context():
        RecordJob().perform_later("registered")
        with pytest.raises(ProgrammerError, match="registered"):
            Job().perform_later()
    jobs.queue_adapter.perform_all()
    assert app.config["EVENTS"] == [("job", "registered", "a")]


@pytest.mark.parametrize("order", [("a", "b"), ("b", "a")])
def test_celery_eager_identical_task_names_use_owning_context(make_app, order):
    apps = {name: make_app(name, adapter=CeleryQueueAdapter) for name in order}
    for app in apps.values():
        jobs = app.extensions["flaskteroids.jobs"]
        jobs.queue_adapter.finalize()
        assert "tests.isolation.jobs.RecordJob" in jobs.queue_adapter.tasks
        jobs.register_job("tests.isolation.jobs.RecordJob", RecordJob)
    for name in ("a", "b", "a"):
        with apps[name].app_context():
            result = RecordJob().perform_later(name)
            assert result.successful()
            NoticeMailer().notice().deliver_later()
    assert apps["a"].config["EVENTS"] == [("job", "a", "a")] * 2
    assert apps["b"].config["EVENTS"] == [("job", "b", "b")]
    assert (
        len(apps["a"].extensions["flaskteroids.mail"].delivery_method.deliveries) == 2
    )
    assert (
        len(apps["b"].extensions["flaskteroids.mail"].delivery_method.deliveries) == 1
    )


def test_delayed_mail_and_builtin_jobs_are_registered_in_each_app(make_app):
    a, b = make_app("a"), make_app("b")
    for app in (a, b, a):
        with app.app_context():
            NoticeMailer().notice().deliver_now()
            NoticeMailer().notice().deliver_later()
            PurgeJob().perform_later(blob_id=999, key="m" * 28, service_name="test")
    with b.app_context():
        a.extensions["flaskteroids.jobs"].queue_adapter.perform_all()
    b.extensions["flaskteroids.jobs"].queue_adapter.perform_all()
    for app, count in ((a, 4), (b, 2)):
        deliveries = app.extensions["flaskteroids.mail"].delivery_method.deliveries
        assert len(deliveries) == count
        assert all(
            message["From"] == f"{app.config['OWNER']}@example.org"
            for message in deliveries
        )
        assert all(
            message.get_content().strip() == app.config["OWNER"]
            for message in deliveries
        )
        jobs = app.extensions["flaskteroids.jobs"]
        jobs.register_job(MessageDeliveryJob.__name__, MessageDeliveryJob)
        jobs.register_job("flaskteroids.attachments.PurgeJob", PurgeJob)


def test_inline_test_jobs_preserve_the_ambient_transaction(make_app):
    class CreateAuthorJob(Job):
        def perform(self):
            Author.create(name="pending", passcode="secret")

    app = make_app("a")
    jobs = app.extensions["flaskteroids.jobs"]
    jobs.register_job("create_author", CreateAuthorJob)
    jobs.queue_adapter.performing_enqueued_jobs = True
    with app.app_context():
        CreateAuthorJob().perform_later()
        assert app.config["EVENTS"] == []
        assert Author.count() == 1
        session.rollback()
    with app.app_context():
        assert Author.count() == 0
    assert app.config["EVENTS"] == [("rollback", "pending")]


def test_purge_jobs_delete_only_the_owning_apps_storage_and_metadata(make_app):
    a, b = make_app("a"), make_app("b")
    for app in (a, b):
        with app.app_context():
            author = Author.create(name=app.config["OWNER"], passcode="secret")
            author.avatar.attach(
                io=BytesIO(app.config["OWNER"].encode()), filename="avatar.txt"
            )
    with a.app_context():
        author = Author.first()
        blob_id = author.avatar.blob.id
        author.avatar.purge_later()
    with b.app_context():
        a.extensions["flaskteroids.jobs"].queue_adapter.perform_all()
        assert Author.first().avatar.download() == b"b"
        assert Blob.find(blob_id).download() == b"b"
    with a.app_context():
        with pytest.raises(RecordNotFoundException):
            Blob.find(blob_id)
        assert not Author.first().avatar.attached()
