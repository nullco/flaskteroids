from app.mailers.application_mailer import ApplicationMailer


class ProductMailer(ApplicationMailer):
    def in_stock(self):
        self.product = self.params["product"]
        self.subscriber = self.params["subscriber"]
        return self.mail(
            to=self.subscriber.email,
            subject=f"{self.product.name} is back in stock",
        )
