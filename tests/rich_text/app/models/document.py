from flaskteroids.model import (
    after_commit,
    after_save,
    has_many,
    has_rich_text,
    validates,
)
from tests.rich_text.app.models.application_model import ApplicationModel


class Document(ApplicationModel):
    has_rich_text("content")
    has_rich_text("summary")
    has_many(
        "notes", class_name="Note", foreign_key="document_id", inverse_of="document"
    )
    after_save("_remember_saved_content")
    after_commit("_remember_committed_content")
    saved_content = None
    committed_content = None

    def _remember_saved_content(self):
        self.saved_content = self.content.to_plain_text()

    def _remember_committed_content(self):
        self.committed_content = self.content.to_plain_text()

    validates("title", presence=True)
    validates("content", presence=True)
