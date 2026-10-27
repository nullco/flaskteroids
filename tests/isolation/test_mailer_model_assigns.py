import pytest
from jinja2 import DictLoader

from flaskteroids.exceptions import SerializationError
from flaskteroids.jobs.adapters import CeleryQueueAdapter
from flaskteroids.testing import TestQueueAdapter
from tests.app.models.user import User
from tests.isolation.mailers.model_notice import ModelNoticeMailer
from tests.isolation.models.records import Author


@pytest.mark.parametrize("adapter", [TestQueueAdapter, CeleryQueueAdapter])
def test_model_mail_uses_the_owning_database_and_loads_associations(make_app, adapter):
    apps = {name: make_app(name, adapter=adapter) for name in ("a", "b")}
    for name, app in apps.items():
        app.jinja_loader = DictLoader(
            {
                "model_notice_mailer/notice.txt": "{{ author.name }}|{{ author.stories[0].title }}"
            }
        )
        queue = app.extensions["flaskteroids.jobs"].queue_adapter
        if adapter is CeleryQueueAdapter:
            queue.finalize()
        with app.app_context():
            author = Author.create(name=name, passcode="secret")
            author.stories.create(title=f"{name} story")
            ModelNoticeMailer.with_params(author=author).notice().deliver_later()
    if adapter is TestQueueAdapter:
        with apps["b"].app_context():
            for app in apps.values():
                app.extensions["flaskteroids.jobs"].queue_adapter.perform_all()
    for name, app in apps.items():
        message = app.extensions["flaskteroids.mail"].delivery_method.deliveries[0]
        assert message.get_content().strip() == f"{name}|{name} story"


def test_model_mail_rejects_records_from_another_application_registry(app, make_app):
    with app.app_context():
        record = User.create(username="Other registry")
    other = make_app("other")
    with other.app_context(), pytest.raises(SerializationError):
        ModelNoticeMailer.with_params(author=record).notice().deliver_later()
    assert other.extensions["flaskteroids.jobs"].queue_adapter.enqueued_jobs == []
