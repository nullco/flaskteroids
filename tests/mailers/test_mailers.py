import pytest
from flask import current_app

from flaskteroids.mailer import Mailer, init


class UsersMailer(Mailer):
    def welcome(self):
        return self.mail(to="john-doe@example.org", subject="Welcome!")


init(UsersMailer)


@pytest.mark.usefixtures("app_ctx")
def test_deliver_now_sends_mail_to_recipient():
    UsersMailer().welcome().deliver_now()

    deliveries = current_app.extensions["flaskteroids.mail"].delivery_method.deliveries
    assert len(deliveries) == 1
    assert deliveries[0]["To"] == "john-doe@example.org"


@pytest.mark.usefixtures("app_ctx")
def test_deliver_later_enqueues_mail_until_jobs_are_performed():
    adapter = current_app.extensions["flaskteroids.jobs"].queue_adapter
    deliveries = current_app.extensions["flaskteroids.mail"].delivery_method.deliveries

    UsersMailer().welcome().deliver_later()

    assert len(adapter.enqueued_jobs) == 1
    assert deliveries == []
    adapter.perform_all()
    assert len(deliveries) == 1
    assert deliveries[0]["To"] == "john-doe@example.org"
