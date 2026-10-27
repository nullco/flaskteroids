from app.mailers.product_mailer import ProductMailer
from app.models.product import Product
from app.models.subscriber import Subscriber
from test.test_helper import MailerTest


class ModelAssignsTest(MailerTest):
    def test_queued_models_are_visible_inside_transactional_tests(self):
        product = Product.create(name="T-Shirt", inventory_count=0)
        subscriber = Subscriber.create(product=product, email="reader@example.org")
        with self.assert_emails(1), self.perform_enqueued_jobs():
            ProductMailer.with_params(
                product=product, subscriber=subscriber
            ).in_stock().deliver_later()
        assert (
            "T-Shirt is back in stock"
            in self.deliveries[0].get_body(preferencelist=("plain",)).get_content()
        )

    def test_inline_restock_delivery_reads_committed_model_assigns(self):
        product = Product.create(name="T-Shirt", inventory_count=0)
        Subscriber.create(product=product, email="reader@example.org")
        with self.assert_emails(1), self.perform_enqueued_jobs():
            assert product.update(inventory_count=5)
        assert self.deliveries[0]["To"] == "reader@example.org"
