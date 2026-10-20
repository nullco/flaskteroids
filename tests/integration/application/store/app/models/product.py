from app.models.application_model import ApplicationModel

from flaskteroids.model import has_many, validates
from flaskteroids.rules import rules


@rules(
    validates("name", presence=True),
    validates("quantity", numericality={"only_integer": True}),
    has_many("subscribers", dependent="destroy"),
)
class Product(ApplicationModel):
    pass
