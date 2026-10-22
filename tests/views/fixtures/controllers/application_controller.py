from flask import request

from flaskteroids.controller import ActionController, helper_method


class ApplicationController(ActionController):
    helper_method("_viewer")

    def _viewer(self):
        return request.headers.get("X-Viewer", "guest")

    def _unregistered(self):
        return "private controller method"
