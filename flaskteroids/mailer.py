import logging
import smtplib
import ssl
from email.message import EmailMessage
from flask import current_app, render_template
from jinja2 import TemplateNotFound
from flaskteroids import str_utils
from flaskteroids.exceptions import ProgrammerError
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

    def __getattr__(self, name):
        if name.startswith('invoke_'):
            name = name.replace('invoke_', '')

            def wrapper(*args, **kwargs):
                action = getattr(self, name)
                self._action = name
                return action(*args, **kwargs)
            return wrapper

        raise AttributeError(f"{self.__class__.__name__} does not have attribute {name}")

    @classmethod
    def schedule(cls):
        return _MailerScheduler(cls)

    def perform(self, *args, **kwargs):
        action = kwargs.pop('_action')
        getattr(self, f'invoke_{action}')(*args, **kwargs)

    def mail(self, *, to, subject):
        self._msg['Subject'] = subject
        self._msg['From'] = 'no-reply@flaskteroids.me'
        self._msg['To'] = to
        txt = self._render_content(self._build_template_path(type_='txt'))
        html = self._render_content(self._build_template_path(type_='html'))
        if not txt:
            raise ProgrammerError('Make sure you at least have a text/plain template for the mail')
        self._msg.set_content(txt)
        if html:
            self._msg.add_alternative(html, subtype='html')
        self._send()

    def _build_template_path(self, type_: str):
        return f'{str_utils.camel_to_snake(self.__class__.__name__)}/{self._action}.{type_}'

    def _render_content(self, path: str):
        try:
            return render_template(path, **self.__dict__)
        except TemplateNotFound:
            _logger.debug(f'template at <{path}> not found')
            return None

    def _send(self):
        if not current_app.config.get('MAIL_ENABLED', True):
            _logger.debug('sending mail is disabled, ignoring...')
            return
        host = current_app.config['MAIL_HOST']
        port = current_app.config['MAIL_PORT']
        username = current_app.config['MAIL_USERNAME']
        password = current_app.config['MAIL_PASSWORD']

        with smtplib.SMTP(host, port) as server:
            server.starttls()
            server.login(username, password)
            server.send_message(self._msg)
