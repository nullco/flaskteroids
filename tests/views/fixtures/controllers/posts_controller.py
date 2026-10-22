from flask import render_template, request

from tests.views.fixtures.controllers.application_controller import (
    ApplicationController,
)


class PostsController(ApplicationController):
    def show(self):
        self.title = request.headers.get("X-Title", "Posts")
        return render_template("probe.html")
