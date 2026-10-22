import logging
from email.message import EmailMessage
from functools import wraps

from flask import current_app, render_template
from jinja2 import TemplateNotFound

from flaskteroids._view_helpers import helper as helper
from flaskteroids._view_helpers import helper_method as helper_method
from flaskteroids._view_helpers import mailer_scope
from flaskteroids.actions import (
    decorate_action,
    get_actions,
    mark_action_wrapper,
    original_action,
    register_actions,
)
from flaskteroids.declarations import actions_for
from flaskteroids.inflector import inflector
from flaskteroids.jobs.job import Job
from flaskteroids.rules import bind_rules

_logger = logging.getLogger(__name__)


def init(cls):
    definition = actions_for(cls)
    if definition.prepared:
        return cls
    register_actions(cls, ActionMailer)
    bind_rules(cls)
    _decorate_actions(cls)
    definition.prepared = True
    return cls


def _decorate_actions(cls):
    for name in get_actions(cls):
        action = original_action(cls, name)
        setattr(cls, name, _decorate_action(cls, action))


def _decorate_action(cls, action):
    original = action
    action = decorate_action(cls, action)

    @wraps(action)
    def wrapper(*args, **kwargs):
        message_delivery = action(*args, **kwargs)
        assert message_delivery, "Actions must return a MessageDelivery object"
        builder = message_delivery.builder
        if not builder.template_name:
            builder.template_name = action.__name__
        return message_delivery

    return mark_action_wrapper(wrapper, original)


class ActionMailer:
    def mail(self, *, from_=None, to, subject):
        helpers = current_app.extensions.get("flaskteroids.helpers")
        helper_owner = (
            helpers.register_mailer(type(self)) if helpers is not None else None
        )
        return MessageDelivery(
            MessageBuilder(
                from_=from_,
                to=to,
                subject=subject,
                template_path=inflector.underscore(self.__class__.__name__),
                template_params=self.__dict__,
                helper_owner=helper_owner,
            )
        )


class MessageBuilder:
    def __init__(
        self,
        *,
        from_,
        to,
        subject,
        template_path=None,
        template_name=None,
        template_params=None,
        helper_owner=None,
    ):
        defaults = current_app.config.action_mailer.default_options
        self.from_ = from_ or defaults.get("from_") or "no-reply@flaskteroids.me"
        self.to = to
        self.subject = subject
        self.template_path = template_path
        self.template_name = template_name
        self.template_params = template_params or {}
        self.helper_owner = helper_owner

    def build(self):
        msg = EmailMessage()
        msg["Subject"] = self.subject
        msg["From"] = self.from_
        msg["To"] = self.to
        helpers = current_app.extensions.get("flaskteroids.helpers")
        owner = (
            helpers.restore_mailer(self.helper_owner, self.template_params)
            if helpers is not None
            else None
        )
        assigns = vars(owner) if owner is not None else self.template_params
        with mailer_scope(owner, assigns):
            txt = self._render_content(type_="txt", assigns=assigns)
            html = self._render_content(type_="html", assigns=assigns)
        if txt:
            msg.set_content(txt)
        if html:
            msg.add_alternative(html, subtype="html")
        return msg

    def _render_content(self, type_: str, *, assigns):
        path = f"{self.template_path}/{self.template_name}.{type_}"
        try:
            return render_template(path, **assigns)
        except TemplateNotFound:
            _logger.debug(f"template at <{path}> not found")
            return None

    def to_dict(self):
        return self.__dict__

    @classmethod
    def from_dict(cls, d):
        return cls(**d)


class MessageDeliveryJob(Job):
    def perform(self, *args, **kwargs):
        message_builder = MessageBuilder.from_dict(kwargs["message_builder"])
        msg = message_builder.build()
        if not msg:
            _logger.debug("Nothing to send, ignoring...")
            return
        _logger.debug("message to be sent")
        _logger.debug(msg)
        cfg = current_app.config.action_mailer
        if not cfg.perform_deliveries:
            _logger.debug("sending mail is disabled, ignoring...")
            return
        current_app.extensions["flaskteroids.mail"].deliver(msg)


class MessageDelivery:
    def __init__(self, builder: MessageBuilder) -> None:
        self.builder = builder

    def deliver_now(self, *args, **kwargs):
        MessageDeliveryJob().perform(
            *args, message_builder=self.builder.to_dict(), **kwargs
        )

    def deliver_later(self, *args, **kwargs):
        MessageDeliveryJob().perform_later(
            *args, message_builder=self.builder.to_dict(), **kwargs
        )
