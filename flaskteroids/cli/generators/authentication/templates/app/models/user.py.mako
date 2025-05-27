from flaskteroids.rules import rules
from flaskteroids.model import has_many
from app.models.application_model import ApplicationModel


@rules(
    has_many('sessions')
)
class User(ApplicationModel):
    @classmethod
    def authenticate_by(cls, *, email, password):
        return User.find_by(email=email, password=password).first()
