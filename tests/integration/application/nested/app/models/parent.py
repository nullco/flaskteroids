from app.models.application_model import ApplicationModel

from flaskteroids.model import accepts_nested_attributes_for, has_many, validates


class Parent(ApplicationModel):
    has_many("children", dependent="destroy")
    accepts_nested_attributes_for(
        "children", allow_destroy=True, reject_if="all_blank", limit=20
    )
    validates("name", presence=True)
