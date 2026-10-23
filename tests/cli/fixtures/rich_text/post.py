from app.models.application_model import ApplicationModel

from flaskteroids.model import has_rich_text, validates


class Post(ApplicationModel):
    has_rich_text("content")
    validates("title", presence=True)
    validates("content", presence=True)
