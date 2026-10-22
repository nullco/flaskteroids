from flaskteroids.model import has_many, has_secure_password, PasswordAuthenticator
from app.models.application_model import ApplicationModel


class User(ApplicationModel, PasswordAuthenticator):
    has_secure_password()
    has_many('sessions', dependent='destroy')
