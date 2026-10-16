from flask import Flask

from flaskteroids.configuration import Configuration
from flaskteroids.extensions.jobs import JobsExtension
from flaskteroids.jobs.job import Job


def test_application_uses_custom_adapter_and_dynamic_configuration(mocker):
    registrations = []
    enqueued = []
    result = object()

    class CustomAdapter:
        def __init__(self, application, config):
            assert application.config.x.nested.value == "custom"
            assert config.extra.to_dict() == {"mode": "custom"}

        def register(self, job_name, job_class):
            registrations.append((job_name, job_class))

        def enqueue(self, job_class, args, kwargs):
            enqueued.append((job_class, args, kwargs))
            return result

    class CustomJob(Job):
        pass

    app = Flask(__name__)
    app.config = Configuration(app.root_path, app.config)
    app.config.active_job.queue_adapter = CustomAdapter
    app.config.active_job.extra = {"mode": "custom"}
    app.config.x.nested.value = "custom"
    mocker.patch("flaskteroids.extensions.jobs.discover_classes", return_value={})
    jobs = JobsExtension(app)
    jobs.register_job("custom", CustomJob)
    with app.app_context():
        assert CustomJob().perform_later("value", enabled=True) is result
    assert ("custom", CustomJob) in registrations
    assert enqueued == [(CustomJob, ("value",), {"enabled": True})]
