from secrets import token_urlsafe

from app.models.application_model import ApplicationModel

from flaskteroids.model import before_create, belongs_to, validates


class Subscriber(ApplicationModel):
    belongs_to("product")
    validates("email", presence=True)
    before_create("_assign_unsubscribe_token")

    def _assign_unsubscribe_token(self):
        self.unsubscribe_token = token_urlsafe(32)
