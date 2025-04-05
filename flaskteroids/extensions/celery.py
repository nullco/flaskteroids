import logging
import inspect
import pkgutil
import flaskteroids.registry as registry
from celery import Celery
from importlib import import_module
from celery.signals import setup_logging


_logger = logging.getLogger(__name__)


class CeleryExtension:

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

        self._jobs = self._discover_jobs()
        for job_name, job_class in self._jobs.items():

            @self._celery.task(name=f'app.jobs.{job_name}')
            def task_wrapper(*args, **kwargs):
                job_instance = job_class()
                job_instance.perform(*args, **kwargs)

            ns = registry.get(job_class)
            ns['task'] = task_wrapper

        if not hasattr(app, "extensions"):
            app.extensions = {}
        app.extensions["celery"] = self

    def _discover_jobs(self):
        jobs_package = 'app.jobs'
        try:
            package = import_module(jobs_package)
        except ModuleNotFoundError:
            _logger.debug('No jobs module detected... ignoring')
            return {}
        package_path = package.__path__
        jobs = {}
        job = import_module('flaskteroids.jobs.job')
        for _, job_name, _ in pkgutil.iter_modules(package_path):
            absolute_name = f"{jobs_package}.{job_name}"
            module = import_module(absolute_name)
            for name, obj in inspect.getmembers(module, inspect.isclass):
                if issubclass(obj, job.Job) and \
                        obj is not job.Job:
                    jobs[name] = obj
        _logger.debug(f'discovered {len(jobs)} job classes')
        return jobs


    def __getattr__(self, name):
        return getattr(self._celery, name)
