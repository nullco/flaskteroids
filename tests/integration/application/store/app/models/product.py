from app.models.application_model import ApplicationModel

from flaskteroids.model import has_many, validates


class Product(ApplicationModel):
    validates("name", presence=True)
    validates("quantity", numericality={"only_integer": True})
    has_many("subscribers", dependent="destroy")
