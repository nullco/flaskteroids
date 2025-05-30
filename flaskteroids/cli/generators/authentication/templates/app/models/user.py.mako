from flaskteroids.rules import rules
from flaskteroids.model import has_many, has_secure_password, PasswordAuthenticator
from app.models.application_model import ApplicationModel


@rules(
    has_secure_password(),
    has_many('sessions')
)
class User(ApplicationModel, PasswordAuthenticator):
    pass
