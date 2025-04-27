from flaskteroids.extensions.utils import discover_classes
from flaskteroids.mailer import Mailer


class MailExtension:

    def __init__(self, app=None):
        if app:
            self.init_app(app)

    def init_app(self, app):
        if not hasattr(app, "extensions") or 'flaskteroids.jobs' not in app.extensions:
            raise ValueError('Jobs extension not initialized')

        jobs_extension = app.extensions['flaskteroids.jobs']
        self._mailers = discover_classes('app.mailers', Mailer)

        for mailer_name, mailer_class in self._mailers.items():
            jobs_extension.register_job(mailer_name, mailer_class)

        app.extensions["flaskteroids.mail"] = self
