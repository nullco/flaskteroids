from flaskteroids import rules
from flaskteroids.mailer import ActionMailer, helper


@rules(helper("application", "admin/money"))
class NotesMailer(ActionMailer):
    def welcome(self):
        self.title = "Newsletter"
        return self.mail(to="reader@example.com", subject="Welcome")


class PlainMailer(ActionMailer):
    def welcome(self):
        return self.mail(to="reader@example.com", subject="Plain")
