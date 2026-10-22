from app.models.application_model import ApplicationModel

from flaskteroids.callbacks import after_commit
from flaskteroids.model import has_many_attached, has_one_attached


class Member(ApplicationModel):
    has_one_attached("avatar")
    has_many_attached("files")
    after_commit("verify_committed_upload")

    def verify_committed_upload(self):
        assert self.avatar.download().strip() == b"An example attachment."
