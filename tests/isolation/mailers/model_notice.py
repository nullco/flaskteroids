from flaskteroids import params
from flaskteroids.mailer import ActionMailer


class ModelNoticeMailer(ActionMailer):
    def notice(self):
        self.author = params["author"]
        return self.mail(to="reader@example.org", subject="Author update")
