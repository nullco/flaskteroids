from flaskteroids.model import has_rich_text, validates
from tests.rich_text.app.models.application_model import ApplicationModel


class Entry(ApplicationModel):
    has_rich_text("content", encrypted=True)
    has_rich_text("summary", store_if_blank=False)
    has_rich_text("restricted", strict_loading=True)
    validates("title", length={"minimum": 1})
