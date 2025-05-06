from flaskteroids.extensions.utils import discover_classes, discover_methods
from flaskteroids.mailer import ActionMailer
import flaskteroids.registry as registry
from flaskteroids.rules import bind_rules


class MailExtension:

    def __init__(self, app=None):
        if app:
            self.init_app(app)

    def init_app(self, app):
        if not hasattr(app, "extensions") or 'flaskteroids.jobs' not in app.extensions:
            raise ValueError('Jobs extension not initialized')

        jobs_extension = app.extensions['flaskteroids.jobs']
        self._mailers = discover_classes('app.mailers', ActionMailer)

        for mailer_name, mailer_class in self._mailers.items():
            ns = registry.get(mailer_class)
            ns['name'] = mailer_name
            ns['actions'] = discover_methods(
                mailer_class, ignore=set(discover_methods(ActionMailer))
            )
            jobs_extension.register_job(mailer_name, mailer_class)
            bind_rules(mailer_class)

        app.extensions["flaskteroids.mail"] = self
