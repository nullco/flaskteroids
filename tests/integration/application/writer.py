from app.models.application_model import ApplicationModel

from flaskteroids.model import has_many
from flaskteroids.rules import rules


@rules(has_many("stories", dependent="destroy"))
class Writer(ApplicationModel):
    pass
