from app.controllers.application_controller import ApplicationController

from flaskteroids.actions import around_action
from flaskteroids.i18n import InvalidLocale, with_locale


class CatalogController(ApplicationController):
    def _switch_locale(self):
        try:
            with with_locale(self.params.get("locale") or "en"):
                yield
        except InvalidLocale:
            self.head(400)

    around_action("_switch_locale")

    def index(self):
        pass

    def show(self):
        self.render(json={"notice": self.t(".notice")})
