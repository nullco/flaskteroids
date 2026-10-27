from flaskteroids.actions import around_action
from flaskteroids.controller import Controller
from flaskteroids.i18n import InvalidLocale, with_locale


class ProductsController(Controller):
    def _switch_locale(self):
        locale = self.params.get("locale") or "en"
        try:
            with with_locale(locale):
                yield
        except InvalidLocale:
            self.head(400)

    around_action("_switch_locale")

    def index(self):
        pass

    def show(self):
        return self.render(json={"notice": self.t(".notice")})

    def fail(self):
        raise RuntimeError("Locale scope failed")

    def redirect(self):
        self.redirect_to("/products/")
