from app.models.application_model import ApplicationModel

from flaskteroids.model import belongs_to, validates
from flaskteroids.rules import rules


@rules(
    belongs_to("product"),
    validates("email", presence=True, length={"minimum": 10}),
)
class Subscriber(ApplicationModel):
    pass
