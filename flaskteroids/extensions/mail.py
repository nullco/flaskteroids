from flaskteroids.extensions.utils import discover_classes, discover_methods
from flaskteroids.mailer import ActionMailer
import flaskteroids.registry as registry
from flaskteroids.rules import bind_rules


class MailExtension:

    def __init__(self, app=None):
        if app:
            self.init_app(app)

    def init_app(self, app):
        self._mailers = discover_classes('app.mailers', ActionMailer)

        for mailer_name, mailer_class in self._mailers.items():
            ns = registry.get(mailer_class)
            ns['name'] = mailer_name
            ns['actions'] = discover_methods(
                mailer_class, ignore=set(discover_methods(ActionMailer))
            )
            bind_rules(mailer_class)

        app.extensions["flaskteroids.mail"] = self
