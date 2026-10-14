from flask import current_app

from flaskteroids.actions import before_action
from flaskteroids.controller import ActionController
from flaskteroids.rules import rules


@rules(before_action("_record"))
class CounterController(ActionController):
    def _record(self):
        current_app.config["EVENTS"].append("before")

    def index(self):
        current_app.config["EVENTS"].append("action")
        return current_app.config["OWNER"]
