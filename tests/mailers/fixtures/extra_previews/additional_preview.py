from flaskteroids.mailer import MailerPreview
from tests.mailers.fixtures.preview_support import PreviewNoticesMailer


class AdditionalPreview(MailerPreview):
    def welcome(self):
        return PreviewNoticesMailer.with_params().welcome()
