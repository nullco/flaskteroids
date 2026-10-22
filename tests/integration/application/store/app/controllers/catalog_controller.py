from app.controllers.application_controller import ApplicationController

from flaskteroids.actions import skip_before_action


class CatalogController(ApplicationController):
    skip_before_action("_require_authentication", only=["index"])

    def index(self):
        pass

    def edit(self):
        return "Catalog editor"
