import logging

from celery import signals

from flaskteroids.attachments.jobs import PurgeJob
from flaskteroids.discovery import discover_classes
from flaskteroids.exceptions import ProgrammerError
from flaskteroids.jobs.job import Job
from flaskteroids.mailer import MessageDeliveryJob

_logger = logging.getLogger(__name__)


@signals.setup_logging.connect
def _setup_logging(*args, **kwargs):
    # Do not overwrite application logging setup.
    pass


class JobsExtension:
    def __init__(self, app=None):
        self._jobs = {}
        self._names = {}
        self.queue_adapter = None
        if app:
            self.init_app(app)

    def init_app(self, app):
        if vars(self).get("_app", app) is not app:
            raise ProgrammerError(
                "A jobs extension cannot be shared between applications."
            )
        if "flaskteroids.jobs" in app.extensions:
            return
        config = app.config.active_job
        jobs_module = app.config.paths.jobs
        self.queue_adapter = config.queue_adapter(app, config)
        for job_name, job_class in discover_classes(jobs_module, Job).items():
            self.register_job(f"{jobs_module}.{job_name}", job_class)
        self.register_job(MessageDeliveryJob.__name__, MessageDeliveryJob)
        self.register_job("flaskteroids.attachments.PurgeJob", PurgeJob)
        self._app = app
        app.extensions["flaskteroids.jobs"] = self

    def register_job(self, job_name, job_class):
        if job_name in self._jobs:
            if self._jobs[job_name] is job_class:
                return
            raise ProgrammerError(
                f"Job name {job_name!r} is already registered to another class."
            )
        if job_class in self._names:
            raise ProgrammerError(
                f"Job {job_class.__name__} is already registered as {self._names[job_class]!r}."
            )
        self.queue_adapter.register(job_name, job_class)
        self._jobs[job_name] = job_class
        self._names[job_class] = job_name
        _logger.debug("registered task for job %s", job_class)

    def enqueue(self, job_cls, args, kwargs):
        if job_cls not in self._names:
            raise ProgrammerError(
                f"Job {job_cls.__name__} is not registered in this application."
            )
        return self.queue_adapter.enqueue(job_cls, args, kwargs)

    def __getattr__(self, name):
        return getattr(self.queue_adapter, name)
