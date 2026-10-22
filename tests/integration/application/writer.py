from app.models.application_model import ApplicationModel

from flaskteroids.model import has_many


class Writer(ApplicationModel):
    has_many("stories", dependent="destroy")
