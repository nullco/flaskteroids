from app.controllers.application_controller import ApplicationController
from app.models.product import Product
from app.models.subscriber import Subscriber

from flaskteroids import params, redirect_to
from flaskteroids.controller import render
from flaskteroids.routes import product_path


class SubscribersController(ApplicationController):
    def new(self):
        self.product = Product.find(params["product_id"])
        self.subscriber = Subscriber.new(product_id=self.product.id)

    def create(self):
        self.product = Product.find(params["product_id"])
        self.subscriber = Subscriber.new(
            product_id=self.product.id, **params.expect(subscriber=["email"])
        )
        if self.subscriber.save():
            return redirect_to(product_path(self.product))
        return render("new", status=422)

    def edit(self):
        self.product = Product.find(params["product_id"])
        self.subscriber = Subscriber.where(product_id=self.product.id).find(
            params["id"]
        )

    def update(self):
        self.product = Product.find(params["product_id"])
        self.subscriber = Subscriber.where(product_id=self.product.id).find(
            params["id"]
        )
        if self.subscriber.update(**params.expect(subscriber=["email"])):
            return redirect_to(product_path(self.product))
        return render("edit", status=422)
