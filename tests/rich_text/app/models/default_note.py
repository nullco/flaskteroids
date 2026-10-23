from flaskteroids.model import has_rich_text
from tests.rich_text.app.models.application_model import ApplicationModel


class StrictModel(ApplicationModel):
    __abstract__ = True
    strict_loading_by_default = True


class DefaultNote(StrictModel):
    has_rich_text("content")
    has_rich_text("relaxed", strict_loading=False)
