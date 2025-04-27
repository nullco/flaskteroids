from celery import Celery
from celery.signals import setup_logging
import flaskteroids.registry as registry
from flaskteroids.extensions.utils import discover_classes
from flaskteroids.jobs.job import Job


class JobsExtension:

    def __init__(self, app=None):

        # Do not overwrite logging setup.
        setup_logging.connect(lambda *args, **kwargs: ...)

        self._celery = Celery()
        self._jobs = {}
        if app:
            self.init_app(app)

    def init_app(self, app):
        self._celery.main = app.import_name
        conf = app.config.get('JOBS') or {}
        self._celery.conf['result_backend'] = conf.get('CELERY_RESULT_BACKEND')
        self._celery.conf['broker_url'] = conf.get('CELERY_BROKER_URL')
        self._celery.conf.update(conf.get('CELERY_ADDITIONAL_CONFIG') or {})

        class AppContextTask(self._celery.Task):
            def __call__(self, *args, **kwargs):
                with app.app_context():
                    return self.run(*args, **kwargs)

        self._celery.Task = AppContextTask

        self._jobs = discover_classes('app.jobs', Job)
        for job_name, job_class in self._jobs.items():
            self.register_job(f'app.jobs.{job_name}', job_class)
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

    def __getattr__(self, name):
        return getattr(self._celery, name)
