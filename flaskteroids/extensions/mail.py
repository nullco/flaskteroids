from flaskteroids.actions import register_actions
from flaskteroids.discovery import discover_classes
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
            register_actions(mailer_class, ActionMailer)
            bind_rules(mailer_class)

        app.extensions["flaskteroids.mail"] = self
