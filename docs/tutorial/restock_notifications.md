# Add restock notifications

Let visitors ask for an email when a sold-out product becomes available again.
This part of the store tutorial follows one feature from its database tables to
the email a subscriber receives.

After working through this guide, you will know how to:

- Associate subscribers with products.
- Accept public subscriptions and provide unsubscribe links.
- Send a background email after inventory changes commit.

Continue in the `store` application from
[Add login and product images](authentication_and_uploads.md). You will use its
login workflow and product form. Run commands from the application root.

## Notify visitors when products return to stock

Our catalog can describe a product and show its image, but it cannot answer a
shopper's next question: "Can I get one?" Let's track inventory. If a product
sells out, visitors will be able to subscribe to a restock email and unsubscribe
later.

### Track inventory

Stop the server and generate a migration for the existing products table:

```sh
bin/flask generate migration AddInventoryCountToProducts inventory_count:integer
```

Open the new file under `db/migrate/versions/`. In `upgrade()`, change only the
`inventory_count` column to add `nullable=False` and `server_default="0"`:

```python
sa.Column("inventory_count", sa.Integer(), nullable=False, server_default="0")
```

Keep the rest of the migration unchanged. The default gives existing and new
products a count of zero; `nullable=False` prevents null values. These are
inventory-specific choices, not defaults the generator can infer.

Apply it:

```sh
bin/flask db:migrate
```

Replace `app/models/product.py` with the following, preserving the attachment
declaration we added earlier:

```python
from app.models.application_model import ApplicationModel
from flaskteroids.model import has_one_attached, validates


class Product(ApplicationModel):
    validates("name", presence=True)
    validates("inventory_count", numericality={"only_integer": True})
    validates("inventory_count", comparison={"greater_than_or_equal_to": 0})
    has_one_attached(
        "featured_image",
        max_size=2 * 1024 * 1024,
        content_types=["image/png", "image/jpeg"],
    )
```

The database supplies the default; validations explain invalid user input.
Both `inventory_count` declarations apply: repeated `validates` calls add checks
rather than replacing earlier ones.

Add this field before the submit button in `app/views/products/_form.html`:

```html
<div>
  {{ form.label("inventory_count") }}
  {{ form.number_field("inventory_count") }}
</div>
```

Replace `_product_params()` in `ProductsController` so edits can include stock:

```python
    def _product_params(self):
        return self.params.expect(
            product=["name", "description", "featured_image", "inventory_count"]
        )
```

Create `app/views/products/_inventory.html`:

```html
{% if product.inventory_count > 0 %}
  <p>{{ product.inventory_count }} in stock</p>
{% else %}
  <p>Out of stock</p>
{% endif %}
```

Include it after the description in `app/views/products/show.html`:

```html
{% include "products/_inventory.html" %}
```

Restart the server. **Try it:** an existing product should say Out of stock.
Log in, edit its inventory count to 5, and save: the page should say 5 in stock.
Try -1 and check that the form explains the error and keeps the entered value.
Finally set the count to 0 so we can build the subscription experience.

### Remember who wants an email

A product can have many subscribers, and each subscriber belongs to a product.
Generate the subscriber model and its migration:

```sh
bin/flask generate model Subscriber product:references email:string unsubscribe_token:string
```

The reference creates `product_id` and a foreign key. Open the generated
CreateSubscribers migration and add this after `op.create_table(...)` in
`upgrade()`:

```python
    op.create_index(
        "ix_subscribers_unsubscribe_token",
        "subscribers",
        ["unsubscribe_token"],
        unique=True,
    )
```

The generated `downgrade()` drops the table, including its index. Apply the
migration:

```sh
bin/flask db:migrate
```

Replace `app/models/subscriber.py` with:

```python
from secrets import token_urlsafe

from app.models.application_model import ApplicationModel
from flaskteroids.model import before_create, belongs_to, validates


class Subscriber(ApplicationModel):
    belongs_to("product")
    validates("email", presence=True)
    before_create("_assign_unsubscribe_token")

    def _assign_unsubscribe_token(self):
        self.unsubscribe_token = token_urlsafe(32)
```

A `before_create` callback assigns a random token before the record is first
saved. That token will let someone unsubscribe without an account. Treat it
like a credential: do not expose a subscriber list or log the tokens.

In `app/models/product.py`, add `has_many` to the existing model import and add
`has_many("subscribers", dependent="destroy")` inside the model class.
Deleting a product will now delete its subscriptions too.

Restart the server, then open `bin/flask shell`:

```pycon
>>> product = Product.find_by(name="Cotton T-Shirt")
>>> subscriber = Subscriber.create(product=product, email="reader@example.org")
>>> subscriber.product.name
'Cotton T-Shirt'
>>> [person.email for person in product.subscribers]
['reader@example.org']
>>> bool(subscriber.unsubscribe_token)
True
```

The association connects the objects without manually looking up a foreign-key
value. Exit the shell. Next, let's let visitors do this from the product page.

### Add the subscription form

Create `app/controllers/subscribers_controller.py`:

```python
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
```

Subscriptions are public, unlike editing stock. The email is allowlisted, and
the product comes from the URL rather than an editable form field. Looking up
an existing subscription through the product's association avoids adding another
during ordinary repeat visits. `first_or_create()` returns the existing record or
attempts to save a new one using the scope's email and parent. A rejected save
returns its errors and entered values for redisplay. This lookup is not an atomic
uniqueness guarantee; a production signup service also needs database constraints,
confirmation, and abuse controls.

In `config/routes.py`, replace the existing `route.resources("products")`
declaration with the nested resource, keeping your other routes:

```python
    route.resources(
        "products",
        nested=lambda child: child.resources("subscribers", only=["create"]),
    )
```

Product member actions still receive `id`; subscriber creation receives
`product_id`. Python and templates can both use
`product_subscribers_path(product)`.

The nested URL tells the controller which product the visitor wants to follow.
Replace `app/views/products/_inventory.html` with:

```html
{% if product.inventory_count > 0 %}
  <p>{{ product.inventory_count }} in stock</p>
{% else %}
  <p>Out of stock</p>
  <p>Email me when it is available:</p>
  {% call(form) form_with(model=[product, Subscriber.new()]) %}
    {{ form.email_field("email", required=True, placeholder="you@example.org") }}
    {{ form.submit("Notify me") }}
  {% endcall %}
{% endif %}
```

The final model determines field scope and values, so the email is named
`subscriber[email]` automatically. The parent supplies the nested URL binding;
it does not become the field prefix or enable nested-attribute persistence.
The controller filters the child with `self.params.expect(subscriber=["email"])`.

Create `app/views/subscribers/new.html` for invalid submissions:

```html
{% extends layout %}

{% block body %}
  <h1>Follow {{ product.name }}</h1>
  <ul class="errors">
    {% for message in subscriber.errors.full_messages() %}
      <li>{{ message }}</li>
    {% endfor %}
  </ul>
  {% call(form) form_with(model=[product, subscriber]) %}
    {{ form.email_field("email", required=True) }}
    {{ form.submit("Notify me") }}
  {% endcall %}
  {{ link_to("Back", product_path(product)) }}
{% endblock %}
```

Our successful redirect sets a flash notice. In
`app/views/layouts/application.html`, add this just after `<body>`, before the
`body` block:

```html
{% if flash.notice %}<p role="status">{{ flash.notice }}</p>{% endif %}
{% if flash.alert %}<p role="alert">{{ flash.alert }}</p>{% endif %}
```

**Try it:** log out, open an out-of-stock product, and subscribe with another
email address. You should return to the product and see the confirmation.
Subscribe with the same address again: the ordinary repeat request should still
show confirmation, not create another record. In a new shell, select the product
with `product = Product.find_by(name="Cotton T-Shirt")`, then check
`Subscriber.where(product_id=product.id).count()`.

### Let subscribers leave

Before sending notifications, let's give recipients a way to stop them. Add
these routes inside `register` in `config/routes.py`:

```python
    route.get("/unsubscribe/<token>/", to="unsubscribes#show", aka="unsubscribe")
    route.post(
        "/unsubscribe/<token>/", to="unsubscribes#destroy", aka="cancel_subscription"
    )
```

Create `app/controllers/unsubscribes_controller.py`:

```python
from app.controllers.application_controller import ApplicationController
from app.models.subscriber import Subscriber
from flaskteroids.actions import skip_before_action


class UnsubscribesController(ApplicationController):
    skip_before_action("_require_authentication")

    def show(self):
        self.subscriber = Subscriber.find_by(unsubscribe_token=self.params["token"])
        if self.subscriber is None:
            return self.redirect_to("/", notice="This subscription is no longer active.")

    def destroy(self):
        subscriber = Subscriber.find_by(unsubscribe_token=self.params["token"])
        if subscriber is not None:
            subscriber.destroy()
        return self.redirect_to("/", notice="You are unsubscribed.")
```

Create `app/views/unsubscribes/show.html`:

```html
{% extends layout %}

{% block body %}
  <h1>Stop following {{ subscriber.product.name }}?</h1>
  {% call(form) form_with(url=url_for("cancel_subscription", token=subscriber.unsubscribe_token)) %}
    {{ form.submit("Unsubscribe") }}
  {% endcall %}
{% endblock %}
```

Opening an email link displays a confirmation; only submitting its CSRF-protected
POST form removes the subscription. Email link scanners therefore do not
unsubscribe someone just by following a GET request. Invalid or already-used
tokens redirect safely to the catalog.

### Write the restock email

Generate a mailer:

```sh
bin/flask generate mailer Product in_stock
```

Replace `app/mailers/product_mailer.py` with:

```python
from app.mailers.application_mailer import ApplicationMailer


class ProductMailer(ApplicationMailer):
    def in_stock(self):
        self.product = self.params["product"]
        self.subscriber = self.params["subscriber"]
        return self.mail(
            to=self.subscriber.email,
            subject=f"{self.product.name} is back in stock",
        )
```

`with_params(...)` supplies the mailer's `self.params`, using the same API as
controllers without an HTTP request. Instance variables expose the product and
subscriber to templates; queued delivery reloads these saved records.

Email links need absolute URLs: `product_url` is the absolute counterpart of
`product_path`. The custom unsubscribe endpoint still uses `url_for` with
`_external=True`.

Replace `app/views/product_mailer/in_stock.html` with:

```html
<h1>Good news!</h1>
<p>{{ link_to(product.name, product_url(product)) }} is back in stock.</p>
<p>{{ link_to("Unsubscribe", url_for("unsubscribe", token=subscriber.unsubscribe_token, _external=True)) }}</p>
```

Replace `app/views/product_mailer/in_stock.txt` with:

```text
Good news! {{ product.name }} is back in stock.
{{ product_url(product) }}

Unsubscribe: {{ url_for("unsubscribe", token=subscriber.unsubscribe_token, _external=True) }}
```

### Preview delivery locally

We want to see the message without needing a real mailbox. Create
`app/mailers/console_delivery.py`, an application-owned development adapter:

```python
class ConsoleDeliveryMethod:
    def __init__(self, application, config):
        pass

    def deliver(self, message):
        print(f"To: {message['To']}", flush=True)
        print(f"Subject: {message['Subject']}", flush=True)
        print(message.get_body(preferencelist=("plain",)).get_content(), flush=True)
```

Replace `config/environments/development.py` with:

```python
from app.mailers.console_delivery import ConsoleDeliveryMethod


def configure(config):
    config.enable_reloading = True
    config.consider_all_requests_local = True
    config.controller.perform_caching = False
    config.attachments.service = "local"
    config["SERVER_NAME"] = "127.0.0.1:5000"
    config.mailer.perform_deliveries = True
    config.mailer.delivery_method = ConsoleDeliveryMethod
    config.jobs.broker_url = "sqla+sqlite:///storage/jobs_database.db"
```

`SERVER_NAME` supplies a host for absolute links even in the shell. This adapter
prints mail; it does not send real messages. The development queue uses a local
SQLite file, so this example needs no separate broker server.

Restart the web server. Open a new `bin/flask shell` and preview one email:

```python
from app.mailers.product_mailer import ProductMailer

subscriber = Subscriber.find_by(email="reader@example.org")
product = subscriber.product
ProductMailer.with_params(
    product=product, subscriber=subscriber
).in_stock().deliver_now()
```

You should see a readable message preview in the shell, with a subject ending
in "is back in stock", a product link, and an unsubscribe link. Exit the shell.
The action runs immediately; `deliver_later()` queues its captured template
assigns, not `self.params`. See [Mailers](../other/mailers.md) for delivery details.

### Trigger notifications after a restock

Now connect inventory to email. Replace `app/models/product.py` with:

```python
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
    after_commit("_notify_subscribers", on="update", when="_back_in_stock")

    def _back_in_stock(self):
        change = self.saved_change_to_attribute("inventory_count")
        return change is not None and change[0] == 0 and change[1] > 0

    def _notify_subscribers(self):
        for subscriber in self.subscribers:
            ProductMailer.with_params(
                product=self, subscriber=subscriber
            ).in_stock().deliver_later()
```

`saved_change_to_attribute()` returns the old and new typed values from the
latest successful save, or `None` when that attribute did not change. A change
from zero to a positive count triggers one email per subscriber. An ordinary
description edit or a change from 5 to 6 does not send a new batch.

`after_commit` runs only after the outer transaction commits, so a rollback never
enqueues these notifications. The callback can query subscribers normally; the
mailer captures each message's recipient and subject when called, while queued
template models reload at delivery. If an explicit transaction saves the same
product more than once, the condition describes its
last successful save, not every intermediate transition. See
[Models](../models/index.md) for callbacks, saved changes, and transactions.

### Watch the complete feature work

Restart the web server to load the model. From `store`, start a worker in another
terminal:

```sh
bin/jobs start
```

The web process and worker read the same development configuration and local
queue. Keep both running for this checkpoint:

1. Log in and set Cotton T-Shirt's inventory count to 0.
2. Log out and subscribe from its product page with a second email address.
3. Log in again, change the inventory count to 5, and save.
4. Watch the worker terminal: one message per subscribed address should appear.
5. Change the count from 5 to 6. There should be no new restock email.
6. Copy an unsubscribe URL from a message into the browser and confirm removal.
7. Set stock to 0 and then 5 again. That recipient should no longer get an email.

We now have a reason for every piece: inventory drives the page, associations
remember interested visitors, callbacks notice a restock, and a mailer and job
queue deliver the notification outside the request.

The console adapter is for development only. Real delivery needs SMTP settings
and a sender address; production also needs a worker and a suitable shared broker
when running multiple instances. Generated production settings read
`CELERY_BROKER_URL`. See [Mailers](../other/mailers.md), [Background jobs](../other/jobs.md),
and [Configuration](../configuration.md) for those settings.

## Next steps

The store now connects a visitor's subscription to a restock email.
Continue with [Test the store](testing.md) to check the behavior automatically.
