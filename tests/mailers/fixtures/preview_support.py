from flaskteroids.actions import after_action, before_action
from flaskteroids.mailer import ActionMailer, MailerPreview, helper_method


class PreviewNoticesMailer(ActionMailer):
    before_action("_prepare")
    after_action("_finish")
    helper_method("_signature")

    def _prepare(self):
        self.greeting = self.params.get("greeting", "Hello")
        self.name = self.params.get("name", "Jane")

    def _finish(self):
        self.footer = "Prepared by callback"

    def _signature(self):
        return self.footer

    def welcome(self):
        return self.mail(to="jane@example.com", subject=self.greeting)

    def text_only(self):
        return self.mail(to="jane@example.com", subject="Text only")

    def html_only(self):
        return self.mail(to="jane@example.com", subject="HTML only")

    def empty(self):
        return self.mail(to="jane@example.com", subject="Empty")

    def unsafe(self):
        return self.mail(to="jane@example.com", subject=self.greeting)


class BasePreview(MailerPreview):
    def inherited_scenario(self):
        return PreviewNoticesMailer.with_().welcome()
