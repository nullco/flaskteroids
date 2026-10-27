from flaskteroids.mailer import Mailer


class ModelNoticeMailer(Mailer):
    def notice(self):
        self.author = self.params["author"]
        return self.mail(to="reader@example.org", subject="Author update")
