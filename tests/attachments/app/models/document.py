from typing import ClassVar

from flaskteroids.model import (
    after_commit,
    after_save,
    has_many_attached,
    has_one_attached,
    validates,
)
from tests.attachments.app.models.application_model import ApplicationModel


class Document(ApplicationModel):
    validates("title", presence=True)
    has_one_attached("avatar", max_size=256, content_types=["image/png"])
    has_many_attached("files")
    has_one_attached("archive", service="archive", dependent="purge")
    has_one_attached("backup", dependent=None)
    after_commit("_remember_avatar")
    after_save("_remember_saved_blob")
    committed_filenames: ClassVar[list[str]] = []
    committed_contents: ClassVar[list[bytes]] = []
    saved_blob_ids: ClassVar[list[int]] = []

    def _remember_saved_blob(self):
        if self.avatar.attached():
            self.saved_blob_ids.append(self.avatar.blob.id)

    def _remember_avatar(self):
        if self.avatar.attached():
            self.committed_filenames.append(self.avatar.attachment.blob.filename)
            self.committed_contents.append(self.avatar.download())
