from dataclasses import dataclass

from flask import current_app, has_app_context

from flaskteroids.jobs.job import Job


@dataclass(frozen=True)
class EnqueuedJob:
    job_class: type[Job]
    args: tuple
    kwargs: dict


class TestQueueAdapter:
    __test__ = False

    def __init__(self, application, config):
        self.application = application
        self.enqueued_jobs = []
        self.performing_enqueued_jobs = False

    def register(self, job_name, job_class):
        pass

    def enqueue(self, job_class, args, kwargs):
        job = EnqueuedJob(job_class=job_class, args=tuple(args), kwargs=dict(kwargs))
        if self.performing_enqueued_jobs:
            self._perform(job)
        else:
            self.enqueued_jobs.append(job)
        return job

    def perform_all(self):
        while self.enqueued_jobs:
            job = self.enqueued_jobs.pop(0)
            self._perform(job)

    def _perform(self, job):
        if has_app_context() and current_app._get_current_object() is self.application:
            return job.job_class().perform(*job.args, **job.kwargs)
        with self.application.app_context():
            return job.job_class().perform(*job.args, **job.kwargs)

    def clear(self):
        self.enqueued_jobs.clear()
        self.performing_enqueued_jobs = False
