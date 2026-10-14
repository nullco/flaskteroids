from flask import current_app

from flaskteroids.model import (
    Model,
    PasswordAuthenticator,
    after_commit,
    after_rollback,
    belongs_to,
    has_many,
    has_one_attached,
    has_secure_password,
)
from flaskteroids.rules import rules


@rules(
    has_secure_password("passcode"),
    has_many(
        "stories", class_name="Story", foreign_key="author_id", dependent="destroy"
    ),
    has_many("edited_stories", class_name="Story", foreign_key="editor_id"),
    has_one_attached("avatar"),
    after_commit("_committed"),
    after_rollback("_rolled_back"),
)
class Author(Model, PasswordAuthenticator):
    def _committed(self):
        current_app.config["EVENTS"].append(("commit", self.name))

    def _rolled_back(self):
        current_app.config["EVENTS"].append(("rollback", self.name))


@rules(
    belongs_to("author", class_name="Author", foreign_key="author_id"),
    belongs_to("editor", class_name="Author", foreign_key="editor_id"),
)
class Story(Model):
    pass
