from app.models.application_model import ApplicationModel

from flaskteroids.model import validates


class Post(ApplicationModel):
    validates("title", presence=True, length={"minimum": 5})
