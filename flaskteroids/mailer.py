import logging
import smtplib
import ssl
from email.message import EmailMessage
from flask import current_app
from flaskteroids.jobs.job import Job

_logger = logging.getLogger(__name__)


class _MailerScheduler:
    def __init__(self, mailer_cls, action):
        self._mailer_cls = mailer_cls
        self._action = action

    def deliver_now(self, *args, **kwargs):
        kwargs['_action'] = self._action
        mailer = self._mailer_cls()
        return mailer.perform(*args, **kwargs)

    def deliver_later(self, *args, **kwargs):
        kwargs['_action'] = self._action
        mailer = self._mailer_cls()
        mailer.perform_later(*args, **kwargs)


class _MailerMeta(type):

    def __getattribute__(self, name):
        attr = super().__getattribute__(name)
        if isinstance(self, type):
            if callable(attr):
                return _MailerScheduler(self, name)
        return attr


class Mailer(Job, metaclass=_MailerMeta):

    def __init__(self):
        self._msg = EmailMessage()

    def perform(self, *args, **kwargs):
        action = kwargs.pop('_action')
        getattr(self, action)(*args, **kwargs)

    def mail(self, *, to, subject):
        self._msg['Subject'] = subject
        self._msg['From'] = 'no-reply@flaskteroids.me'
        self._msg['To'] = to
        self._msg.set_content("Test email")
        self._send()

    def _send(self):
        if not current_app.config.get('MAIL_ENABLED', True):
            _logger.debug('sending mail is disabled, ignoring...')
            return
        host = current_app.config['MAIL_HOST']
        port = current_app.config['MAIL_PORT']
        username = current_app.config['MAIL_USERNAME']
        password = current_app.config['MAIL_PASSWORD']

        context = ssl.create_default_context()

        with smtplib.SMTP_SSL(host, port, context=context) as server:
            server.login(username, password)
            server.send_message(self._msg)
