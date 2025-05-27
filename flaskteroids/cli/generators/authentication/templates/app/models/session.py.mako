from flaskteroids.rules import rules
from flaskteroids.model import belongs_to
from app.models.application_model import ApplicationModel


@rules(
    belongs_to('user')
)
class Session(ApplicationModel):
    pass
