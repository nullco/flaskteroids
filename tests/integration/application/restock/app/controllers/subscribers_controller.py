from app.controllers.application_controller import ApplicationController
from app.models.product import Product

from flaskteroids.actions import skip_before_action
from flaskteroids.routes import product_path


class SubscribersController(ApplicationController):
    skip_before_action("_require_authentication")

    def create(self):
        self.product = Product.find(self.params["product_id"])
        self.subscriber = self.product.subscribers.where(
            **self.params.expect(subscriber=["email"])
        ).first_or_create()
        if not self.subscriber.is_persisted():
            return self.render("new", status=422)
        return self.redirect_to(
            product_path(self.product),
            notice="We will email you when it is back in stock.",
        )
