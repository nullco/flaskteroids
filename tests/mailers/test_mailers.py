import pytest
from flaskteroids.mailer import init, ActionMailer


class UsersMailer(ActionMailer):
    def welcome(self):
        return self.mail(to='john-doe@example.org', subject='Welcome!')


init(UsersMailer)


@pytest.mark.usefixtures('app_ctx')
def test_deliver_now():
    UsersMailer().welcome().deliver_now()


@pytest.mark.usefixtures('app_ctx')
def test_deliver_later():
    UsersMailer().welcome().deliver_later()
