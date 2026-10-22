from flaskteroids.controller import ActionController
from tests.attachments.app.models.document import Document


class DocumentsController(ActionController):
    def create(self):
        document = Document.create(
            **self.params.expect(document=["title", "avatar", ("files", [])])
        )
        return {"id": document.id, "errors": document.errors.full_messages()}
