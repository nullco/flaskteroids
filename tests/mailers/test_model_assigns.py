import json

import pytest
from flask import current_app
from jinja2 import DictLoader

from flaskteroids import params
from flaskteroids.actions import before_action
from flaskteroids.exceptions import DeserializationError, SerializationError
from flaskteroids.mailer import ActionMailer, MessageDeliveryJob, helper_method
from tests.app.models.user import User


class RecordsMailer(ActionMailer):
    before_action("_count_invocation")
    helper_method("_label")
    helper_method("_context_report")

    def _count_invocation(self):
        current_app.config["mailer_invocations"] = (
            current_app.config.get("mailer_invocations", 0) + 1
        )

    def notice(self):
        self.record = params["record"]
        self.context = params.get("context", {})
        return self.mail(
            to="reader@example.org", subject=f"About {self.record.username}"
        )

    def _label(self):
        return self.record.username

    def _context_report(self):
        return {
            "tuple_preserved": isinstance(self.context["records"], tuple),
            "same_record": self.context["records"][0] is self.record,
            "nested_record": self.context["nested"][0]["record"] is self.record,
            "user_mapping": self.context["mapping"],
        }


@pytest.fixture
def mail_app(app):
    app.jinja_loader = DictLoader(
        {"records_mailer/notice.txt": "{{ record.username }}|{{ label() }}"}
    )
    return app


def deliveries(app):
    return app.extensions["flaskteroids.mail"].delivery_method.deliveries


def test_immediate_delivery_renders_unsaved_model_assigns(mail_app):
    with mail_app.app_context():
        record = User.new(username="Draft")
        RecordsMailer.with_params(record=record).notice().deliver_now()
        assert deliveries(mail_app)[0].get_content().strip() == "Draft|Draft"
        assert record.is_new_record()


@pytest.mark.parametrize("destroyed", [False, True])
def test_queued_delivery_rejects_models_without_persisted_records(mail_app, destroyed):
    with mail_app.app_context():
        record = (
            User.create(username="Reader") if destroyed else User.new(username="Draft")
        )
        if destroyed:
            assert record.destroy()
        with pytest.raises(SerializationError):
            RecordsMailer.with_params(record=record).notice().deliver_later()
        assert (
            mail_app.extensions["flaskteroids.jobs"].queue_adapter.enqueued_jobs == []
        )
        assert deliveries(mail_app) == []


def test_queued_model_assigns_reload_saved_values_without_rerunning_actions(mail_app):
    with mail_app.app_context():
        record = User.create(username="Original")
        RecordsMailer.with_params(record=record).notice().deliver_later()
        queue = mail_app.extensions["flaskteroids.jobs"].queue_adapter
        assert record.update(username="Saved")
        record.username = "Unsaved input"
        queue.perform_all()
        message = deliveries(mail_app)[0]
        assert message["Subject"] == "About Original"
        assert message.get_content().strip() == "Saved|Saved"
        assert mail_app.config["mailer_invocations"] == 1
        assert record.username == "Unsaved input"
        assert User.find(record.id) is record


def test_queued_rendering_preserves_the_callers_application_lifecycle(mail_app):
    teardowns = []

    @mail_app.teardown_appcontext
    def record_teardown(error):
        teardowns.append(error)

    with mail_app.app_context():
        record = User.create(username="Reader")
        RecordsMailer.with_params(record=record).notice().deliver_later()
        mail_app.extensions["flaskteroids.jobs"].queue_adapter.perform_all()
        assert teardowns == []
    assert teardowns


def test_model_assigns_survive_json_transport_and_restore_nested_containers(mail_app):
    mail_app.jinja_loader.mapping["records_mailer/notice.txt"] = (
        "{{ context_report()|tojson }}"
    )
    with mail_app.app_context():
        record = User.create(username="Reader")
        mapping = {"_flaskteroids_mail_value": ["model", "user-supplied", [123]]}
        RecordsMailer.with_params(
            record=record,
            context={
                "records": (record,),
                "nested": [{"record": record}],
                "mapping": mapping,
            },
        ).notice().deliver_later()
        queue = mail_app.extensions["flaskteroids.jobs"].queue_adapter
        payload = json.loads(json.dumps(queue.enqueued_jobs[0].kwargs))
        queue.clear()
        MessageDeliveryJob().perform(**payload)
        assert json.loads(deliveries(mail_app)[0].get_content()) == {
            "tuple_preserved": True,
            "same_record": True,
            "nested_record": True,
            "user_mapping": mapping,
        }


def test_deleted_model_assigns_fail_delivery_explicitly(mail_app):
    with mail_app.app_context():
        record = User.create(username="Reader")
        RecordsMailer.with_params(record=record).notice().deliver_later()
        assert record.destroy()
        with pytest.raises(DeserializationError):
            mail_app.extensions["flaskteroids.jobs"].queue_adapter.perform_all()
        assert deliveries(mail_app) == []
        assert mail_app.config["mailer_invocations"] == 1
