import logging
from celery import Celery
from celery import signals
import flaskteroids.registry as registry
from flaskteroids.discovery import discover_classes
from flaskteroids.mailer import MessageDeliveryJob
from flaskteroids.jobs.job import Job

_logger = logging.getLogger(__name__)


# Do not overwrite logging setup.
@signals.setup_logging.connect
def _setup_logging(*args, **kwargs):
    pass


class JobsExtension:

    def __init__(self, app=None):
        self._celery = Celery()
        self._jobs = {}
        if app:
            self.init_app(app)

    def init_app(self, app):
        self._celery.main = app.import_name
        conf = app.config.get('JOBS') or {}
        jobs_module = app.config['JOBS']['LOCATION']
        self._celery.conf['result_backend'] = conf.get('CELERY_RESULT_BACKEND')
        self._celery.conf['broker_url'] = conf.get('CELERY_BROKER_URL')
        self._celery.conf.update(conf.get('CELERY_ADDITIONAL_CONFIG') or {})

        class AppContextTask(self._celery.Task):
            def __call__(self, *args, **kwargs):
                with app.app_context():
                    return self.run(*args, **kwargs)

        self._celery.Task = AppContextTask

        self._jobs = discover_classes(jobs_module, Job)
        for job_name, job_class in self._jobs.items():
            self.register_job(f'{jobs_module}.{job_name}', job_class)
        self.register_job(MessageDeliveryJob.__name__, MessageDeliveryJob)
        if not hasattr(app, "extensions"):
            app.extensions = {}
        app.extensions["flaskteroids.jobs"] = self

    def register_job(self, job_name, job_class):

        @self._celery.task(name=job_name)
        def task_wrapper(*args, **kwargs):
            job_instance = job_class()
            job_instance.perform(*args, **kwargs)

        ns = registry.get(job_class)
        ns['task'] = task_wrapper
        _logger.debug(f'registered task for job {job_class}')

    def __getattr__(self, name):
        return getattr(self._celery, name)
