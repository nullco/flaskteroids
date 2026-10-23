from flaskteroids.model import belongs_to, has_rich_text
from tests.rich_text.app.models.application_model import ApplicationModel


class Note(ApplicationModel):
    has_rich_text("content")
    belongs_to("document", foreign_key="document_id", inverse_of="notes", optional=True)
