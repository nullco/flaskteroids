from app.models.application_model import ApplicationModel

from flaskteroids.model import has_many, validates


class Person(ApplicationModel):
    has_many("memberships", dependent="destroy")
    has_many("organizations", through="memberships")
    validates("name", presence=True)
