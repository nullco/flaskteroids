from app.models.application_model import ApplicationModel

from flaskteroids.model import encrypts, validates


class Account(ApplicationModel):
    encrypts("email", deterministic=True)
    encrypts("notes")

    validates("name", presence=True)
