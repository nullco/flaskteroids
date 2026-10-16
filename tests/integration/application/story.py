from app.models.application_model import ApplicationModel

from flaskteroids.model import belongs_to, validates
from flaskteroids.rules import rules


@rules(belongs_to("writer"), validates("title", presence=True))
class Story(ApplicationModel):
    pass
