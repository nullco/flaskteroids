from flaskteroids.model import validates
from flaskteroids.rules import rules

from .application_model import ApplicationModel


@rules(
    validates("name", presence=True),
    validates("quantity", numericality={"only_integer": True, "allow_nil": True}),
)
class Product(ApplicationModel):
    pass


@rules(validates("email", presence=True))
class Subscriber(ApplicationModel):
    pass


class Category(ApplicationModel):
    def to_param(self):
        return self.slug if self.is_persisted() else None
