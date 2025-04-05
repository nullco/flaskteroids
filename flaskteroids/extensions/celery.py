from celery import Celery
from celery.signals import setup_logging


@setup_logging.connect
def avoid_logging_reconfiguration(*args, **kwags):
    """ This registers an empty custom logging configuration function in order to prevent celery to re-configure logs.
    Logs are only reconfigured by celery if there are no custom logging configurators
    """
    pass


class CeleryExtension:

    def __init__(self, app=None):
        self._celery = Celery()
        if app:
            self.init_app(app)

    def init_app(self, app):
        self._celery.main = app.import_name
        self._celery.conf['result_backend'] = app.config['CELERY_RESULT_BACKEND']
        self._celery.conf['broker_url'] = app.config['CELERY_BROKER_URL']
        self._celery.conf.update(app.config['CELERY_ADDITIONAL_CONFIG'])

        class ContextTask(self._celery.Task):
            def __call__(self, *args, **kwargs):
                with app.app_context():
                    return self.run(*args, **kwargs)

        self._celery.Task = ContextTask

        if not hasattr(app, "extensions"):
            app.extensions = {}
        app.extensions["celery"] = self

    def __getattr__(self, name):
        return getattr(self._celery, name)
