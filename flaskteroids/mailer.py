import logging
import smtplib
from functools import wraps
from email.message import EmailMessage
from flask import current_app, render_template
from jinja2 import TemplateNotFound
from flaskteroids.jobs.job import Job
from flaskteroids.actions import decorate_action, get_actions, register_actions
from flaskteroids.rules import bind_rules
from flaskteroids.inflector import inflector

_logger = logging.getLogger(__name__)


def init(cls):
    register_actions(cls, ActionMailer)
    bind_rules(cls)
    _decorate_actions(cls)
    return cls


def _decorate_actions(cls):
    for name in get_actions(cls):
        action = getattr(cls, name)
        setattr(cls, name, _decorate_action(cls, action))


def _decorate_action(cls, action):
    action = decorate_action(cls, action)

    @wraps(action)
    def wrapper(*args, **kwargs):
        message_delivery = action(*args, **kwargs)
        assert message_delivery, 'Actions must return a MessageDelivery object'
        builder = message_delivery.builder
        if not builder.template_name:
            builder.template_name = action.__name__
        return message_delivery
    return wrapper


class ActionMailer:

    def mail(self, *, from_=None, to, subject):
        return MessageDelivery(
            MessageBuilder(
                from_=from_,
                to=to,
                subject=subject,
                template_path=inflector.underscore(self.__class__.__name__),
                template_params=self.__dict__
            )
        )


class MessageBuilder:
    def __init__(self, *,
                 from_, to, subject,
                 template_path=None,
                 template_name=None,
                 template_params=None):
        self.from_ = from_ or 'no-reply@flaskteroids.me'  # TODO: Make it configurable
        self.to = to
        self.subject = subject
        self.template_path = template_path
        self.template_name = template_name
        self.template_params = template_params or {}

    def build(self):
        msg = EmailMessage()
        msg['Subject'] = self.subject
        msg['From'] = self.from_
        msg['To'] = self.to
        txt = self._render_content(type_='txt')
        html = self._render_content(type_='html')
        if txt:
            msg.set_content(txt)
        if html:
            msg.add_alternative(html, subtype='html')
        return msg

    def _render_content(self, type_: str):
        path = f'{self.template_path}/{self.template_name}.{type_}'
        try:
            return render_template(path, **self.template_params)
        except TemplateNotFound:
            _logger.debug(f'template at <{path}> not found')
            return None

    def to_dict(self):
        return self.__dict__

    @classmethod
    def from_dict(cls, d):
        return cls(**d)


class MessageDeliveryJob(Job):

    def perform(self, *args, **kwargs):
        message_builder = MessageBuilder.from_dict(kwargs['message_builder'])
        msg = message_builder.build()
        if not msg:
            _logger.debug('Nothing to send, ignoring...')
            return
        _logger.debug('message to be sent')
        _logger.debug(msg)
        cfg = current_app.config['MAILERS']
        if not cfg.get('SEND_MAILS', True):
            _logger.debug('sending mail is disabled, ignoring...')
            return
        host = cfg['MAIL_HOST']
        port = cfg['MAIL_PORT']
        username = cfg['MAIL_USERNAME']
        password = cfg['MAIL_PASSWORD']

        with smtplib.SMTP(host, port) as server:
            server.starttls()
            server.login(username, password)
            server.send_message(msg)


class MessageDelivery:

    def __init__(self, builder: MessageBuilder) -> None:
        self.builder = builder

    def deliver_now(self, *args, **kwargs):
        MessageDeliveryJob().perform(*args, message_builder=self.builder.to_dict(), **kwargs)

    def deliver_later(self, *args, **kwargs):
        MessageDeliveryJob().perform_later(*args, message_builder=self.builder.to_dict(), **kwargs)
