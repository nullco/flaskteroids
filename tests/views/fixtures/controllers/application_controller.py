from flask import request

from flaskteroids.controller import Controller, helper_method


class ApplicationController(Controller):
    helper_method("_viewer")

    def _viewer(self):
        return request.headers.get("X-Viewer", "guest")

    def _unregistered(self):
        return "private controller method"
