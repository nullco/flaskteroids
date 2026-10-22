from app.mailers.application_mailer import ApplicationMailer

from flaskteroids import params


class ProductMailer(ApplicationMailer):
    def in_stock(self):
        self.product = params["product"]
        self.subscriber = params["subscriber"]
        return self.mail(
            to=self.subscriber.email,
            subject=f"{self.product.name} is back in stock",
        )
