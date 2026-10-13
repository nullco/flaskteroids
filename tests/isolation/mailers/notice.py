from flaskteroids.mailer import ActionMailer


class NoticeMailer(ActionMailer):
    def notice(self):
        return self.mail(to="reader@example.org", subject="notice")
