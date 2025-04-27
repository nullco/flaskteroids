import logging
import smtplib
import ssl
from email.message import EmailMessage
from flask import current_app
from flaskteroids.jobs.job import Job

_logger = logging.getLogger(__name__)

_internal_attrs = {
    '_method', '_msg', '_send',
    'mail', 'perform', 'perform_later',
    'deliver_now', 'deliver_later'
}


class Mailer(Job):

    def __init__(self):
        self._msg = EmailMessage()
        self._method = None

    def __getattribute__(self, name: str):
        attr = super().__getattribute__(name)
        if not callable(attr) or name in _internal_attrs:
            return attr
        self._method = name
        return self

    def perform(self, *args, **kwargs):
        if not self._method:
            self._method = kwargs.pop('_method')
        getattr(self, self._method)(*args, **kwargs)

    def deliver_now(self, *args, **kwargs):
        self.perform(*args, **kwargs)

    def perform_later(self, *args, **kwargs):
        assert self._method
        kwargs['_method'] = self._method
        super().perform_later(*args, **kwargs)

    def deliver_later(self, *args, **kwargs):
        self.perform_later(*args, **kwargs)

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
