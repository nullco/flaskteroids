from app.models.application_model import ApplicationModel

from flaskteroids.model import belongs_to, validates


class Subscriber(ApplicationModel):
    belongs_to("product")
    validates("email", presence=True, length={"minimum": 10})
