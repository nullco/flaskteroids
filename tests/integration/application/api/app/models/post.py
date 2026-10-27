from app.models.application_model import ApplicationModel

from flaskteroids.model import before_destroy, validates


class Post(ApplicationModel):
    validates("title", presence=True)
    before_destroy("_allow_deletion")

    def _allow_deletion(self):
        if self.title == "Protected":
            self.errors.append(("base", "This post is protected"))
            return False
        return True
