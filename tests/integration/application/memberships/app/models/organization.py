from app.models.application_model import ApplicationModel

from flaskteroids.model import accepts_nested_attributes_for, has_many, validates


class Organization(ApplicationModel):
    has_many("memberships", dependent="destroy")
    has_many("members", through="memberships", source="person")
    accepts_nested_attributes_for("memberships", allow_destroy=True)
    validates("name", presence=True)
