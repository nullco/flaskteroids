from flaskteroids.model import validates

from .application_model import ApplicationModel


class Product(ApplicationModel):
    validates("name", presence=True)
    validates("quantity", numericality={"only_integer": True, "allow_nil": True})


class Subscriber(ApplicationModel):
    validates("email", presence=True)


class Fish(ApplicationModel):
    pass


class Equipment(ApplicationModel):
    pass


class Category(ApplicationModel):
    def to_param(self):
        return self.slug if self.is_persisted() else None
