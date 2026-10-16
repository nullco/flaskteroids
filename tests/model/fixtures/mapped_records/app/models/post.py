from flaskteroids.model import belongs_to, validates
from flaskteroids.rules import rules

from .application_model import ApplicationModel


@rules(belongs_to("author"), validates("title", presence=True))
class Post(ApplicationModel):
    pass
