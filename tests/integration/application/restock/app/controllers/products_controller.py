from app.controllers.application_controller import ApplicationController
from app.models.product import Product

from flaskteroids import params
from flaskteroids.actions import skip_before_action


class ProductsController(ApplicationController):
    skip_before_action("_require_authentication")

    def show(self):
        self.product = Product.find(params["id"])
