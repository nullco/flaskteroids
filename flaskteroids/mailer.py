import logging
import smtplib
import ssl
from email.message import EmailMessage
from flask import current_app, render_template
import flaskteroids.registry as registry
from flaskteroids.jobs.job import Job

_logger = logging.getLogger(__name__)


class _MailerScheduler:
    def __init__(self, mailer_cls):
        self._mailer_cls = mailer_cls

    def __getattr__(self, name):
        getattr(self._mailer_cls, name)
        self._action = name
        return self

    def deliver_now(self, *args, **kwargs):
        assert self._action, 'Action not set'
        kwargs['_action'] = self._action
        mailer = self._mailer_cls()
        return mailer.perform(*args, **kwargs)

    def deliver_later(self, *args, **kwargs):
        assert self._action, 'Action not set'
        kwargs['_action'] = self._action
        mailer = self._mailer_cls()
        mailer.perform_later(*args, **kwargs)


class Mailer(Job):

    def __init__(self):
        self._msg = EmailMessage()
        self._action = None

    @classmethod
    def builder(cls):
        return _MailerScheduler(cls)

    def perform(self, *args, **kwargs):
        self._action = kwargs.pop('_action')
        getattr(self, self._action)(*args, **kwargs)

    def mail(self, *, to, subject):
        # ns = registry.get(self.__class__)
        # view_template = render_template(f'{ns["name"]}/{self._action}.html', **self.__dict__)
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
