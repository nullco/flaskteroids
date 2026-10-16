from app.models.application_model import ApplicationModel

from flaskteroids.model import validates
from flaskteroids.rules import rules


@rules(validates("title", presence=True))
class Post(ApplicationModel):
    pass
