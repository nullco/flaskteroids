from flaskteroids.mailer import Mailer


class NoticeMailer(Mailer):
    def notice(self):
        return self.mail(to="reader@example.org", subject="notice")
