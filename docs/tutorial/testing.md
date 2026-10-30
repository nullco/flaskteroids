# Test the store

You have tried the store in a browser. Now turn its main behaviors into automated
checks, from saving a product to delivering a restock email.

After working through this guide, you will know how to:

- Set up related records with fixtures.
- Test models, email, and public request behavior.
- Follow a signed-in user's journey in a browser test.

Continue in the `store` application after completing
[Restock notifications](restock_notifications.md). The examples use its
`Subscriber` model, inventory callbacks, and mailer. Run commands from the
application root.

## Test the store's behavior

We have exercised the store in a browser. Let's turn its important behaviors
into repeatable tests: valid products save, guests can subscribe but cannot edit,
and restocking emails the right people.

Tests use a separate `test` environment and database. `bin/flask test` applies
pending migrations and runs pytest-based tests. Framework test classes roll back
their database changes between tests. The test mail and queue adapters keep
messages in memory, so you do not need the development worker or real SMTP.

### Give the tests a small catalog

Create `test/fixtures/products.yml`:

```yaml
shirt:
  name: T-Shirt
  description: A comfortable cotton shirt.
  inventory_count: 0
```

Create `test/fixtures/subscribers.yml`:

```yaml
reader:
  product: shirt
  email: reader@example.org
  unsubscribe_token: reader-test-token

another:
  product: shirt
  email: another@example.org
  unsubscribe_token: another-test-token
```

Fixture labels connect subscribers to `shirt` without hard-coded IDs. These
example tokens belong only to the test database; real subscriptions generate
random ones. Declare both fixture sets in tests that need the association.

### Test products and restock notifications

Replace `test/models/product_test.py` with:

```python
from test.test_helper import ModelTest

import pytest

from app.models.product import Product


class ProductTest(ModelTest):
    fixtures = ["products", "subscribers"]

    def test_save_persists_valid_product(self):
        product = Product.new(name="Socks", description="Warm socks.")

        assert product.save()
        assert Product.find(product.id).name == "Socks"

    def test_save_rejects_blank_name(self):
        product = Product.new(name="")

        assert not product.save()
        assert product.errors
        assert product.id is None

    def test_inventory_rejects_negative_input(self):
        product = Product.new(name="Socks", inventory_count=-1)

        assert not product.save()
        assert product.inventory_count == -1
        assert product.errors

    def test_restock_emails_subscribers(self):
        product = self.products("shirt")

        with self.assert_emails(2), self.perform_enqueued_jobs():
            assert product.update(inventory_count=5)

        assert {message["To"] for message in self.deliveries} == {
            "reader@example.org",
            "another@example.org",
        }

    def test_positive_stock_adjustment_preserves_notification_count(self):
        product = self.products("shirt")
        assert product.update(inventory_count=5)

        with self.assert_emails(0), self.perform_enqueued_jobs():
            assert product.update(inventory_count=6)

    def test_rolled_back_restock_keeps_queue_empty(self):
        product = self.products("shirt")

        with pytest.raises(ValueError, match="Cancel restock"):
            with Product.transaction():
                assert product.update(inventory_count=5)
                assert not self.enqueued_jobs
                raise ValueError("Cancel restock")

        assert not self.enqueued_jobs
```

The notification test changes stock from zero to five and performs jobs as they
are enqueued. It checks the recipients as well as the count. The other cases
check that ordinary stock adjustments and rolled-back updates do not produce
restock notifications.

Run just these tests:

```sh
bin/flask test test/models/product_test.py
```

You should see them pass without contacting a broker or mail server.

### Check the actual email

Replace the generated `test/mailers/product_mailer_test.py` with:

```python
from test.test_helper import MailerTest

from app.mailers.product_mailer import ProductMailer


class ProductMailerTest(MailerTest):
    fixtures = ["products", "subscribers"]

    def test_email_contains_product_and_unsubscribe_links(self):
        product = self.products("shirt")
        subscriber = self.subscribers("reader")

        with self.assert_emails(1):
            ProductMailer.with_params(
                product=product, subscriber=subscriber
            ).in_stock().deliver_now()

        message = self.deliveries[0]
        assert message["To"] == subscriber.email
        assert message["Subject"] == "T-Shirt is back in stock"
        text = message.get_body(preferencelist=("plain",)).get_content()
        assert f"/products/{product.id}" in text
        assert f"/unsubscribe/{subscriber.unsubscribe_token}/" in text
```

### Check guest access and subscriptions

Replace `test/controllers/products_controller_test.py` with:

```python
from test.test_helper import IntegrationTest, get, post

from app.models.subscriber import Subscriber
from flaskteroids.routes import new_product_path, new_session_path, products_path


class ProductsControllerTest(IntegrationTest):
    fixtures = ["products", "subscribers"]

    def test_guest_can_browse_products(self):
        get(products_path())

        self.assert_response("success")

    def test_guest_is_redirected_to_login(self):
        get(new_product_path())

        self.assert_redirected_to(new_session_path())

    def test_guest_can_subscribe_to_product(self):
        product = self.products("shirt")

        with self.assert_difference(Subscriber.count):
            post(
                f"/products/{product.id}/subscribers",
                params={"subscriber": {"email": "new-reader@example.org"}},
            )

        assert Subscriber.find_by(
            product_id=product.id, email="new-reader@example.org"
        )

    def test_unsubscribe_link_requires_confirmation(self):
        subscriber = self.subscribers("reader")
        path = f"/unsubscribe/{subscriber.unsubscribe_token}/"

        with self.assert_difference(Subscriber.count, by=0):
            get(path)
        self.assert_response("success")

        with self.assert_difference(Subscriber.count, by=-1):
            post(path)
        self.assert_redirected_to("/")
```

The request helpers simulate HTTP without starting a web server. Checking both
GET and POST makes the unsubscribe boundary explicit: following the email link
is safe; confirming the form removes the subscription.

### Walk through an edit in a real browser

Create `test/system/products_test.py`:

```python
from test.test_helper import SystemTest

from app.models.user import User
from flaskteroids.routes import new_product_path


class ProductsTest(SystemTest):
    def setup(self):
        User.create(
            email_address="owner@example.org",
            password="test-password-only",
            password_confirmation="test-password-only",
        )

    def test_owner_creates_and_edits_product(self):
        self.visit(new_product_path())
        self.page.get_by_placeholder("Enter your email address").fill("owner@example.org")
        self.page.locator('input[name="password"]').fill("test-password-only")
        self.click_on("Sign in")
        self.assert_selector("h1", text="New product")

        self.fill_in("Name", value="Browser hat")
        self.fill_in("Description", value="A hat created in the browser.")
        self.click_on("Save product")
        self.assert_selector("h1", text="Browser hat")

        self.click_on("Edit")
        self.fill_in("Name", value="Updated browser hat")
        self.click_on("Save product")
        self.assert_selector("h1", text="Updated browser hat")
```

The test follows the login flow rather than constructing a session cookie. Its
password is fixed test data, not an account used in development or production.
Browser tests use Playwright. Install Chromium once, then run the suite:

```sh
.venv/bin/playwright install chromium
bin/flask test:system
```

You should see the browser journey pass. Run all non-browser tests too:

```sh
bin/flask test
```

The generated health and authentication tests should pass alongside the tests
we wrote. You now have checks for the whole story, from editing a product to
subscribing and delivering its restock email. See [Testing](../testing.md) for
uploads, additional assertions, and running selected tests in parallel.

## Next steps

You now have repeatable checks for the store's main workflows.
Continue with [Prepare the store for deployment](deployment.md) to review
security, continuous integration, and production setup.
