from flaskteroids.model import belongs_to, validates

from .application_model import ApplicationModel


class Post(ApplicationModel):
    belongs_to("author")
    validates("title", presence=True)
