from app.models.application_model import ApplicationModel

from flaskteroids.model import belongs_to, validates


class Child(ApplicationModel):
    belongs_to("parent")
    validates("name", presence=True)
    validates("quantity", numericality={"only_integer": True})
