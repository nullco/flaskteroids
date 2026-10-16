from flaskteroids.model import (
    PasswordAuthenticator,
    after_commit,
    after_rollback,
    after_save,
    before_save,
    has_many,
    has_secure_password,
    validates,
)
from flaskteroids.rules import rules

from .application_model import ApplicationModel


@rules(
    validates("name", presence=True),
    validates("age", numericality={"only_integer": True, "allow_nil": True}),
    has_many("posts", dependent="destroy"),
    has_secure_password(),
    after_commit("_committed"),
    before_save("before_persist"),
    after_save("after_persist"),
    after_rollback("rolled_back"),
)
class Author(ApplicationModel, PasswordAuthenticator):
    def before_persist(self):
        from flask import current_app

        callback = current_app.config.get("before_persist")
        return callback(self) if callback else None

    def after_persist(self):
        from flask import current_app

        callback = current_app.config.get("after_persist")
        if callback:
            callback(self)

    def rolled_back(self):
        from flask import current_app

        current_app.config.setdefault("rollbacks", []).append(self.name)

    def _committed(self):
        from flask import current_app

        current_app.config.setdefault("commits", []).append(self.name)
        callback = current_app.config.get("committed")
        if callback:
            callback(self)
