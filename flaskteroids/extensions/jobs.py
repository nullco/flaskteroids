import logging

from celery import signals

import flaskteroids.registry as registry
from flaskteroids.discovery import discover_classes
from flaskteroids.mailer import MessageDeliveryJob
from flaskteroids.jobs.job import Job

_logger = logging.getLogger(__name__)


@signals.setup_logging.connect
def _setup_logging(*args, **kwargs):
    # Do not overwrite application logging setup.
    pass


class JobsExtension:
    def __init__(self, app=None):
        self._jobs = {}
        self.queue_adapter = None
        if app:
            self.init_app(app)

    def init_app(self, app):
        config = app.config.active_job
        jobs_module = app.config.paths.jobs
        self.queue_adapter = config.queue_adapter(app, config)
        self._jobs = discover_classes(jobs_module, Job)
        for job_name, job_class in self._jobs.items():
            self.register_job(f"{jobs_module}.{job_name}", job_class)
        self.register_job(MessageDeliveryJob.__name__, MessageDeliveryJob)
        app.extensions["flaskteroids.jobs"] = self

    def register_job(self, job_name, job_class):
        self.queue_adapter.register(job_name, job_class)
        registry.get(job_class)["queue_adapter"] = self.queue_adapter
        _logger.debug("registered task for job %s", job_class)

    def __getattr__(self, name):
        return getattr(self.queue_adapter, name)
