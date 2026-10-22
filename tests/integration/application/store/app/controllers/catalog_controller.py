from app.controllers.application_controller import ApplicationController

from flaskteroids import rules
from flaskteroids.actions import skip_before_action


@rules(skip_before_action("_require_authentication", only=["index"]))
class CatalogController(ApplicationController):
    def index(self):
        pass

    def edit(self):
        return "Catalog editor"
