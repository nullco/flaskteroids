from flask import request

from flaskteroids import rules
from flaskteroids.controller import ActionController, helper_method


@rules(helper_method("_viewer"))
class ApplicationController(ActionController):
    def _viewer(self):
        return request.headers.get("X-Viewer", "guest")

    def _unregistered(self):
        return "private controller method"
