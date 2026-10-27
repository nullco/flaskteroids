import json
from types import SimpleNamespace

import pytest
from jinja2 import DictLoader

from flaskteroids.actions import after_action, around_action, before_action, get_actions
from flaskteroids.controller import Controller
from flaskteroids.mailer import Mailer, MessageDeliveryJob, helper_method, init


class NoticesMailer(Mailer):
    before_action("_prepare")
    around_action("_around")
    after_action("_finish")
    helper_method("_signature")

    def _prepare(self, *args, **kwargs):
        self.name = self.params["recipient"].name
        self.steps = ["before"]

    def _around(self, *args, **kwargs):
        self.steps.append(self.params.get("label", "around"))
        try:
            yield
        finally:
            self.steps.append("finished")

    def _finish(self, *args, **kwargs):
        self.footer = self.params.pop("label", "Regards")
        self.params.pop("recipient")
        self.steps.append("after")

    def welcome(self, greeting="Hello", *, punctuation="!"):
        if self.params.get("fail"):
            raise ValueError("Invalid notice")
        self.greeting = f"{greeting}, {self.name}{punctuation}"
        return self.mail(to=self.params["recipient"].email, subject=self.greeting)

    def _signature(self):
        return self.footer + (":leaked params" if self.params else "")


class PersonalNoticesMailer(NoticesMailer):
    pass


class RelayMailer(Mailer):
    def notice(self):
        try:
            NoticesMailer.with_params(
                recipient=self.params["inner"], fail=self.params["inner_fails"]
            ).welcome().deliver_now()
        except ValueError:
            if not self.params["handle_failure"]:
                raise
        return self.mail(to=self.params["recipient"].email, subject="Outer notice")


class CountersMailer(Mailer):
    def notice(self):
        self.params["count"] = self.params.get("count", 0) + 1
        return self.mail(to="reader@example.org", subject=str(self.params["count"]))


@pytest.fixture
def mail_app(app):
    app.jinja_loader = DictLoader(
        {
            f"{name}/welcome.{part}": (
                "{{ greeting }}|{{ signature() }}|{{ steps|join(',') }}|"
                "{{ params is defined }}"
            )
            for name in ("notices_mailer", "personal_notices_mailer")
            for part in ("txt", "html")
        }
    )
    return app


@pytest.fixture
def reader():
    return SimpleNamespace(name="Reader", email="reader@example.org")


def test_mailer_params_are_instance_owned_without_an_application_context():
    first = Mailer()
    second = Mailer()
    first.params["name"] = "Reader"
    assert first.params == {"name": "Reader"}
    assert second.params == {}


def test_plain_mailer_instances_keep_their_own_params(mail_app):
    init(CountersMailer)
    first = CountersMailer()
    second = CountersMailer()
    with mail_app.app_context():
        first.notice().deliver_now()
        first.notice().deliver_now()
        second.notice().deliver_now()
        delivered = mail_app.extensions["flaskteroids.mail"].delivery_method.deliveries
        assert [mail["Subject"] for mail in delivered] == ["1", "2", "1"]


@pytest.mark.parametrize("delivery", ["deliver_now", "deliver_later"])
@pytest.mark.parametrize("in_request", [False, True])
def test_parameterized_actions_and_callbacks_use_mailer_inputs(
    mail_app, reader, delivery, in_request
):
    configured = NoticesMailer.with_params(recipient=reader, label="Thanks")
    context = (
        mail_app.test_request_context("/") if in_request else mail_app.app_context()
    )
    with context:
        if in_request:
            controller = Controller()
            controller.params["recipient"] = "HTTP input"
        message = configured.welcome("Hi", punctuation="?")
        getattr(message, delivery)()
        if delivery == "deliver_later":
            mail_app.extensions["flaskteroids.jobs"].queue_adapter.perform_all()
        delivered = mail_app.extensions["flaskteroids.mail"].delivery_method.deliveries[
            -1
        ]
        assert delivered["To"] == reader.email
        for part in ("plain", "html"):
            assert delivered.get_body(preferencelist=(part,)).get_content().strip() == (
                "Hi, Reader?|Thanks|before,Thanks,finished,after|False"
            )
        if in_request:
            assert controller.params["recipient"] == "HTTP input"


def test_reusing_parameterized_mailers_creates_fresh_action_instances(mail_app, reader):
    configured = NoticesMailer.with_params(recipient=reader)
    with mail_app.app_context():
        first = configured.welcome()
        reader.name = "Second reader"
        second = configured.welcome()
        first.deliver_now()
        second.deliver_now()
        delivered = mail_app.extensions["flaskteroids.mail"].delivery_method.deliveries
        assert [mail["Subject"] for mail in delivered] == [
            "Hello, Reader!",
            "Hello, Second reader!",
        ]


def test_parameterized_delivery_queues_only_captured_assigns(mail_app, reader):
    with mail_app.app_context():
        NoticesMailer.with_params(recipient=reader).welcome().deliver_later()
        queue = mail_app.extensions["flaskteroids.jobs"].queue_adapter
        payload = json.loads(json.dumps(queue.enqueued_jobs[0].kwargs))
        queue.clear()
        reader.email = "changed@example.org"
        reader.name = "Changed"
        MessageDeliveryJob().perform(**payload)
        delivered = mail_app.extensions["flaskteroids.mail"].delivery_method.deliveries[
            -1
        ]
        assert delivered["To"] == "reader@example.org"
        assert delivered["Subject"] == "Hello, Reader!"


def test_failed_parameterized_invocations_preserve_controller_params(mail_app, reader):
    failed = NoticesMailer.with_params(recipient=reader, fail=True)
    with mail_app.test_request_context("/"):
        controller = Controller()
        controller.params["recipient"] = "HTTP input"
        with pytest.raises(ValueError, match="Invalid notice"):
            failed.welcome()
        assert controller.params["recipient"] == "HTTP input"
        NoticesMailer.with_params(recipient=reader).welcome().deliver_now()
        delivered = mail_app.extensions["flaskteroids.mail"].delivery_method.deliveries[
            -1
        ]
        assert delivered["To"] == reader.email


@pytest.mark.parametrize("inner_fails", [False, True])
def test_nested_mailers_preserve_outer_mailer_params(mail_app, reader, inner_fails):
    inner = SimpleNamespace(name="Inner", email="inner@example.org")
    with mail_app.test_request_context("/"):
        controller = Controller()
        controller.params["recipient"] = "HTTP input"
        RelayMailer.with_params(
            recipient=reader, inner=inner, inner_fails=inner_fails, handle_failure=True
        ).notice().deliver_now()
        delivered = mail_app.extensions["flaskteroids.mail"].delivery_method.deliveries
        assert delivered[-1]["To"] == reader.email
        assert controller.params["recipient"] == "HTTP input"


def test_nested_mailer_failures_preserve_controller_params(mail_app, reader):
    with mail_app.test_request_context("/"):
        controller = Controller()
        controller.params["recipient"] = "HTTP input"
        with pytest.raises(ValueError, match="Invalid notice"):
            RelayMailer.with_params(
                recipient=reader, inner=reader, inner_fails=True, handle_failure=False
            ).notice()
        assert controller.params["recipient"] == "HTTP input"


@pytest.mark.parametrize("delivery", ["deliver_now", "deliver_later"])
def test_render_failures_preserve_controller_params(mail_app, reader, delivery):
    mail_app.jinja_loader.mapping["notices_mailer/welcome.html"] = "{{ 1 / 0 }}"
    with mail_app.test_request_context("/"):
        controller = Controller()
        controller.params["recipient"] = "HTTP input"
        message = NoticesMailer.with_params(recipient=reader).welcome()
        with pytest.raises(ZeroDivisionError):
            getattr(message, delivery)()
            if delivery == "deliver_later":
                mail_app.extensions["flaskteroids.jobs"].queue_adapter.perform_all()
        assert controller.params["recipient"] == "HTTP input"


def test_subclasses_inherit_parameterization_and_action_callbacks(mail_app, reader):
    with mail_app.app_context():
        PersonalNoticesMailer.with_params(recipient=reader).welcome().deliver_now()
        delivered = mail_app.extensions["flaskteroids.mail"].delivery_method.deliveries[
            -1
        ]
        assert (
            "before,around,finished,after"
            in delivered.get_body(preferencelist=("plain",)).get_content()
        )


@pytest.mark.parametrize(
    "name", ["mail", "params", "with_params", "_prepare", "missing"]
)
def test_parameterized_mailers_expose_registered_actions_only(reader, name):
    configured = NoticesMailer.with_params(recipient=reader)
    with pytest.raises(AttributeError):
        getattr(configured, name)
    assert "with_params" not in get_actions(init(NoticesMailer))
