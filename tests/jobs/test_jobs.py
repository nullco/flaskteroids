import pytest
from flask import current_app

from flaskteroids.jobs.job import Job


class ExampleJob(Job):
    performed = []

    def perform(self, value):
        self.performed.append(value)


@pytest.mark.usefixtures("app_ctx")
def test_test_adapter_records_and_performs_jobs():
    extension = current_app.extensions["flaskteroids.jobs"]
    extension.register_job("example", ExampleJob)
    adapter = extension.queue_adapter

    ExampleJob().perform_later("value")

    assert len(adapter.enqueued_jobs) == 1
    assert adapter.enqueued_jobs[0].job_class is ExampleJob
    adapter.perform_all()
    assert ExampleJob.performed == ["value"]
    ExampleJob.performed.clear()
