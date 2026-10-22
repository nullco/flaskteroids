from app.models.application_model import ApplicationModel

from flaskteroids.model import belongs_to, validates


class Story(ApplicationModel):
    belongs_to("writer")
    validates("title", presence=True)
