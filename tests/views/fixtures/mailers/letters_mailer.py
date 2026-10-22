from flaskteroids import rules
from flaskteroids.mailer import ActionMailer, helper, helper_method


@rules(
    helper("letters"),
    helper_method("_greeting"),
    helper_method("_next_number", name="delivery_number"),
)
class LettersMailer(ActionMailer):
    def __init__(self, recipient):
        self.recipient = recipient
        self._number = 0

    def welcome(self):
        return self.mail(to="reader@example.com", subject="Letter")

    def _greeting(self, prefix, *, punctuation):
        return f"{prefix} {self.recipient}{punctuation}"

    def _next_number(self):
        self._number += 1
        return self._number


class PersonalLettersMailer(LettersMailer):
    def _greeting(self, prefix, *, punctuation):
        return super()._greeting(prefix, punctuation=punctuation) + " from Notes"
