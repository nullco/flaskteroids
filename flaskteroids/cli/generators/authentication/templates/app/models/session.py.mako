from app.models.application_model import ApplicationModel
from flaskteroids.model import belongs_to


class Session(ApplicationModel):
    belongs_to('user')
