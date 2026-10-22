from app.mailers.application_mailer import ApplicationMailer
from flask import url_for

from flaskteroids.routes import product_url


class ProductMailer(ApplicationMailer):
    def in_stock(self, product, subscriber):
        self.product_name = product.name
        self.product_url = product_url(product)
        self.unsubscribe_url = url_for(
            "unsubscribe", token=subscriber.unsubscribe_token, _external=True
        )
        return self.mail(
            to=subscriber.email, subject=f"{product.name} is back in stock"
        )
