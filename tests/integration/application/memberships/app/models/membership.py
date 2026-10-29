from app.models.application_model import ApplicationModel

from flaskteroids.model import after_validation, belongs_to, validates


class Membership(ApplicationModel):
    belongs_to("organization")
    belongs_to("person")
    validates("role", length={"maximum": 20})
    after_validation("_check_access")

    def _check_access(self):
        if self.person is not None and self.person.name == "Blocked":
            self.errors.append(("person", "This person cannot join"))
