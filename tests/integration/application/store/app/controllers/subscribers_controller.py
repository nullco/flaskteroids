from app.controllers.application_controller import ApplicationController
from app.models.product import Product
from app.models.subscriber import Subscriber

from flaskteroids.routes import product_path


class SubscribersController(ApplicationController):
    def new(self):
        self.product = Product.find(self.params["product_id"])
        self.subscriber = Subscriber.new(product_id=self.product.id)

    def create(self):
        self.product = Product.find(self.params["product_id"])
        self.subscriber = Subscriber.new(
            product_id=self.product.id, **self.params.expect(subscriber=["email"])
        )
        if self.subscriber.save():
            return self.redirect_to(product_path(self.product))
        return self.render("new", status=422)

    def edit(self):
        self.product = Product.find(self.params["product_id"])
        self.subscriber = Subscriber.where(product_id=self.product.id).find(
            self.params["id"]
        )

    def update(self):
        self.product = Product.find(self.params["product_id"])
        self.subscriber = Subscriber.where(product_id=self.product.id).find(
            self.params["id"]
        )
        if self.subscriber.update(**self.params.expect(subscriber=["email"])):
            return self.redirect_to(product_path(self.product))
        return self.render("edit", status=422)
