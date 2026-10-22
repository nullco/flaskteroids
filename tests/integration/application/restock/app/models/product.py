from app.mailers.product_mailer import ProductMailer
from app.models.application_model import ApplicationModel

from flaskteroids.model import (
    after_commit,
    has_many,
    has_one_attached,
    validates,
)


class Product(ApplicationModel):
    validates("name", presence=True)
    validates("inventory_count", numericality={"only_integer": True})
    validates("inventory_count", comparison={"greater_than_or_equal_to": 0})
    has_one_attached(
        "featured_image",
        max_size=2 * 1024 * 1024,
        content_types=["image/png", "image/jpeg"],
    )
    has_many("subscribers", dependent="destroy")
    after_commit("_notify_subscribers", on="update", if_="_back_in_stock")

    def _back_in_stock(self):
        change = self.saved_change_to_attribute("inventory_count")
        return change is not None and change[0] == 0 and change[1] > 0

    def _notify_subscribers(self):
        for subscriber in self.subscribers:
            ProductMailer().in_stock(self, subscriber).deliver_later()
