from flask import current_app

from flaskteroids.actions import before_action
from flaskteroids.controller import Controller


class CounterController(Controller):
    before_action("_record")

    def _record(self):
        current_app.config["EVENTS"].append("before")

    def index(self):
        current_app.config["EVENTS"].append("action")
        return current_app.config["OWNER"]
