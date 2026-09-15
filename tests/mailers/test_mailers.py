import pytest
from flask import current_app
from flaskteroids.mailer import init, ActionMailer


class UsersMailer(ActionMailer):
    def welcome(self):
        return self.mail(to='john-doe@example.org', subject='Welcome!')


init(UsersMailer)


@pytest.mark.usefixtures('app_ctx')
def test_deliver_now():
    UsersMailer().welcome().deliver_now()

    deliveries = current_app.extensions['flaskteroids.mail'].delivery_method.deliveries
    assert len(deliveries) == 1
    assert deliveries[0]['To'] == 'john-doe@example.org'


@pytest.mark.usefixtures('app_ctx')
def test_deliver_later():
    UsersMailer().welcome().deliver_later()
