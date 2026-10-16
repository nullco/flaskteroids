from app.models.application_model import ApplicationModel
from flaskteroids.model import belongs_to
from flaskteroids.rules import rules


@rules(belongs_to('user'))
class Session(ApplicationModel):
    pass
