# Getting started with Flaskteroids

This guide walks you through building a small product catalog called `store`.
You will create records, display them in a browser, build forms, require login
for changes, attach product images, and send email.

By the end, you will know how to:

- Create and run a Flaskteroids application.
- Work with models, migrations, and validations.
- Follow a request through routes, controllers, and views.
- Build a complete create, read, update, and delete (CRUD) interface.
- Add authentication, uploads, and background email delivery.
- Test your application and prepare it for deployment.

You need basic Python and HTML knowledge, but no prior experience with Flask,
SQLAlchemy, or Celery. The examples introduce Flaskteroids APIs and conventions
as you build the application.

## 1. The Flaskteroids approach

Flaskteroids is a Python MVC framework built with Flask, SQLAlchemy, and Celery. It gives these components a shared application structure and workflow.
Two ideas guide that workflow:

- **Convention over configuration:** names and directories tell the framework
  where your models, controllers, templates, and jobs belong.
- **Don't repeat yourself:** migrations describe database structure; models
  describe behavior; reusable templates and callbacks keep shared logic together.

You can use the underlying libraries when needed, but ordinary application work
should not require managing ORM mappings or database sessions yourself.

## 2. Create your application

### Prerequisites

Install these tools before continuing:

- Python 3.12 or newer.
- Git and Bash.
- [uv](https://docs.astral.sh/uv/getting-started/installation/).
- A code editor.

The shell commands in this guide assume a POSIX environment, such as Linux,
macOS, or Windows through WSL. SQLite is included with Python; you do not need a
separate database server for this tutorial.

Start by creating and activating a virtual environment, then install
Flaskteroids:

```sh
python3 -m venv flaskteroids-env
source flaskteroids-env/bin/activate
pip install flaskteroids
```

Generate your application in a new directory:

```sh
flaskteroids new store
cd store
```

The generator creates the project, installs its dependencies with uv into its
own `.venv`, and prepares the development database. It also creates encrypted
credentials and a local master key.

From now on, run commands **inside `store`**, using `bin/flask`. This wrapper
uses the application's virtual environment automatically, so you do not need to
activate it in each terminal. You can explore commands with:

```sh
bin/flask --help
bin/flask generate --help
```

If you used `flaskteroids new store --skip-install`, run `bin/setup` before
continuing. Use that same setup command on a fresh checkout. Commit `uv.lock` so
other developers and deployment builds use the same dependency versions. Never
commit `config/master.key`.

### A quick directory tour

Open the generated directory in your editor:

| Path | Purpose |
| --- | --- |
| `app/models/` | Data behavior, validations, and associations. |
| `app/controllers/` | Actions that handle requests. |
| `app/views/` | Jinja HTML and email templates. |
| `app/helpers/` | Reusable template helpers. |
| `app/mailers/`, `app/jobs/` | Email actions and background work. |
| `app/assets/` | Stylesheets, images, and other source assets. |
| `config/routes.py` | URL-to-action mappings. |
| `config/database.yml` | Database connections by environment. |
| `config/environments/` | Development, test, and production settings. |
| `db/migrate/` | Database migration history. |
| `db/schema.py` | Generated snapshot of the migrated database. |
| `test/` | Tests and fixtures. |
| `storage/` | Local databases and uploaded files. |
| `bin/` | Application commands and setup/release scripts. |
| `deploy/README.md` | Generated Docker and deployment instructions. |

See [Project structure](project_structure.md) for the complete layout.

### Model, view, controller

Most of our work will happen in three places:

- A **model** represents application data and its rules: a `Product`, for example.
- A **controller** handles a request, loads or changes data, and chooses a response.
- A **view** turns the controller's data into HTML.

Routes connect a browser's request to the right controller action. We will build
all of these pieces rather than start with a scaffold, so you can see how they
fit together.

## 3. Hello, Flaskteroids!

Start the development server:

```sh
bin/flask run --debug
```

Open <http://127.0.0.1:5000>. You should see the Flaskteroids welcome page. This
confirms that the generated application boots and serves requests.

Keep the server in one terminal and run other commands in another terminal in
`store`. Press `Ctrl-C` to stop the server. Debug mode reloads changed Python code
and provides an interactive debugger; use it only on your own development machine.

Flaskteroids discovers components in their conventional directories. Python
imports are still explicit: a controller imports the models it uses. After
migrations, stop and restart the server so it loads the new schema snapshot.

## 4. Create a product model

Stop the server and generate a model:

```sh
bin/flask generate model Product name:string description:text
```

This creates:

- `app/models/product.py`: the behavioral model.
- A migration under `db/migrate/versions/`: instructions for creating the table.
- `test/models/product_test.py`: a starting point for model tests.

Use singular CamelCase for model names. `Product` maps to the plural table
`products` by convention.

### Understand the migration

Open the generated migration. Its `upgrade()` function creates `products` with
`name` and `description` columns, an integer primary key `id`, and timestamps
`created_at` and `updated_at`. Its `downgrade()` function drops the table.

Migrations record structural changes so every environment can apply them in
order. Review generated migrations before running them, especially when removing
data or adding constraints.

Apply the migration:

```sh
bin/flask db:prepare
```

`db:prepare` creates the database if necessary and applies pending migrations.
It then regenerates `db/schema.py`. The generated database configuration uses
`storage/development.sqlite3` for development and a separate database for tests.

Open `app/models/product.py`:

```python
from app.models.application_model import ApplicationModel


class Product(ApplicationModel):
    pass
```

An empty model is useful! Its mapped attributes come from the schema snapshot.
We add application behavior here without repeating its column definitions.

**Commit migrations and `db/schema.py`, but do not edit the snapshot by hand.**
Future database changes belong in new migrations. `bin/flask db:rollback` undoes
the most recent migration; a rollback that drops data cannot recover that data.

## 5. Work with records in the shell

Open an application-aware Python shell:

```sh
bin/flask shell
```

Run the following Python examples there. The shell provides an application
context and makes your application models available automatically, so you can
use `Product` directly without importing it.

### Create and query

```python
product = Product.new(name="T-Shirt", description="A comfortable cotton shirt.")
product.save()
product.id
```

`new()` builds an unsaved object. `save()` validates and persists it, returning
`True` on success. You can also build and save in one call:

```python
Product.create(name="Pants", description="Everyday trousers.")
```

`create()` returns the object, including when validation fails. Check its errors
rather than assuming every returned object was saved.

Try a few queries:

```python
list(Product.all())
Product.count()
Product.find(product.id)
Product.find_by(name="T-Shirt")
list(Product.where(name="Pants").order(name="asc"))
```

`all()` and `where()` return lazy queries; iteration or `list()` loads their
records. `find()` raises `RecordNotFoundException` if the record is absent;
`find_by()` returns `None`. Queries are immutable: keep the result when chaining
filters or ordering.

### Update and delete

```python
product.update(name="Cotton T-Shirt")

product.description = "Available in several colors."
product.save()

temporary = Product.create(name="Sample", description="For this example only.")
temporary.destroy()
```

Assignments alone do not save a record. A standalone `save()`, `create()`,
`update()`, or `destroy()` commits before returning; no extra session or commit
call is needed. For operations that must succeed together, use
`with Product.transaction():`; see [Models](models/index.md#assignment-validation-and-persistence).

### Add validation

Exit the shell with `exit()`. Replace `app/models/product.py` with:

```python
from app.models.application_model import ApplicationModel
from flaskteroids.model import validates
from flaskteroids.rules import rules


@rules(validates("name", presence=True))
class Product(ApplicationModel):
    pass
```

`@rules` collects declarations such as validations, associations, and callbacks.
This rule requires a nonblank name. It does not change the database structure,
so there is no migration to run.

Open a **new** `bin/flask shell` so it loads the edited model:

```python
product = Product.new(name="", description="Still available for redisplay.")
product.save()
product.errors.full_messages()
```

The save returns `False`, and `full_messages()` explains the validation failure.
The object retains the submitted description so a form can display it again.
You can fix the object and retry:

```python
product.name = "Socks"
product.save()
exit()
```

Invalid scalar updates also retain their input without publishing it to the
database. Validation is not a substitute for database constraints; add those
through migrations when required by your data model.

## 6. Follow a request through the application

Our product data exists, but it has no web interface yet. A page request follows
this path:

```text
GET /products/
  → config/routes.py
  → ProductsController.index()
  → Product.all()
  → app/views/products/index.html
  → HTML response
```

### Define resource routes

Replace `config/routes.py` with:

```python
def register(route):
    route.get("/up/", to="flaskteroids/health#show")
    route.root(to="products#index")
    route.resources("products")
```

Keep the generated `/up/` health route and the parameter name `route`, which
other generators use when adding routes. The root route makes the catalog our
home page. `resources()` creates the standard CRUD routes:

| Method | Path | Action | Purpose |
| --- | --- | --- | --- |
| GET | `/products/` | `index` | List products. |
| GET | `/products/new/` | `new` | Display a creation form. |
| POST | `/products/` | `create` | Save a new product. |
| GET | `/products/<int:id>/` | `show` | Display one product. |
| GET | `/products/<int:id>/edit/` | `edit` | Display an editing form. |
| PUT/PATCH | `/products/<int:id>/` | `update` | Save changes. |
| DELETE | `/products/<int:id>/` | `destroy` | Delete a product. |

GET retrieves information. POST creates it, PUT/PATCH updates it, and DELETE
removes it. Notice the trailing slashes in resource paths.

Inspect the application's routes with:

```sh
bin/flask routes
```

Routes identify actions with `"controller#action"`: `products#index` means
`ProductsController.index`. The framework discovers that class in
`app/controllers/products_controller.py`.

### Generate a controller

```sh
bin/flask generate controller Products index --skip-routes
```

The generator creates a controller, helper, index template, and controller test.
`--skip-routes` avoids adding routes because we already defined them.

Replace `app/controllers/products_controller.py` with:

```python
from app.controllers.application_controller import ApplicationController
from app.models.product import Product


class ProductsController(ApplicationController):
    def index(self):
        self.products = Product.all()
```

When an action returns `None`, Flaskteroids renders its matching template.
Controller instance variables become template variables: `self.products` is
available as `products`.

Replace `app/views/products/index.html` with:

```html
{% extends "layouts/application.html" %}

{% block body %}
  <h1>Products</h1>
  <ul>
    {% for product in products %}
      <li>{{ product.name }}</li>
    {% else %}
      <li>No products yet.</li>
    {% endfor %}
  </ul>
{% endblock %}
```

Jinja's `{% ... %}` tags control the template, while `{{ ... }}` outputs a value.
The layout supplies the surrounding HTML; this template fills its `body` block.

Run `bin/flask run --debug` again and visit <http://127.0.0.1:5000>. You should see
the products you created in the shell.

## 7. Build the CRUD interface

Now we will add the remaining actions and views. The complete controller below
is the version to use for this stage. Replace
`app/controllers/products_controller.py` with:

```python
from app.controllers.application_controller import ApplicationController
from app.models.product import Product
from flaskteroids import params, redirect_to
from flaskteroids.actions import before_action
from flaskteroids.controller import render
from flaskteroids.routes import product_path, products_path
from flaskteroids.rules import rules


@rules(before_action("_set_product", only=["show", "edit", "update", "destroy"]))
class ProductsController(ApplicationController):
    def index(self):
        self.products = Product.all()

    def show(self):
        pass

    def new(self):
        self.product = Product.new()

    def edit(self):
        pass

    def create(self):
        self.product = Product.new(**self._product_params())
        if self.product.save():
            return redirect_to(product_path(self.product))
        return render("new", status=422)

    def update(self):
        if self.product.update(**self._product_params()):
            return redirect_to(product_path(self.product))
        return render("edit", status=422)

    def destroy(self):
        self.product.destroy()
        return redirect_to(products_path(), status=303)

    def _set_product(self):
        self.product = Product.find(params["id"])

    def _product_params(self):
        return params.expect(product=["name", "description"])
```

### Show a product

The `_set_product` callback loads a record before `show`, `edit`, `update`, or
`destroy`. For `/products/1/`, `params["id"]` is `1`. Extracting that lookup keeps
it out of each action.

Create `app/views/products/show.html`:

```html
{% extends "layouts/application.html" %}

{% block body %}
  <h1>{{ product.name }}</h1>
  <p>{{ product.description }}</p>
  {{ link_to("Back", url_for("index_product")) }}
  {{ link_to("Edit", url_for("edit_product", id=product.id)) }}
  {% call(form) form_with(url=url_for("destroy_product", id=product.id), method="DELETE") %}
    {{ form.submit("Delete") }}
  {% endcall %}
{% endblock %}
```

In templates, `url_for("show_product", id=product.id)` builds a URL from its
named endpoint. Endpoint names appear in `bin/flask routes`. In Python, the
`flaskteroids.routes` module also provides helpers such as `product_path(product)`.
`link_to` creates a link. The `form_with` block creates a deletion form with a
CSRF token and hidden method override. Unlike GET links, these forms can safely
perform state-changing requests.

Replace `app/views/products/index.html` with:

```html
{% extends "layouts/application.html" %}

{% block body %}
  <h1>Products</h1>
  {{ link_to("New product", url_for("new_product")) }}
  <ul>
    {% for product in products %}
      <li>{{ link_to(product.name, url_for("show_product", id=product.id)) }}</li>
    {% else %}
      <li>No products yet.</li>
    {% endfor %}
  </ul>
{% endblock %}
```

### Share a form between new and edit

Create `app/views/products/_form.html`:

```html
{% call(form) form_with(model=product) %}
  {% if product.errors %}
    <ul class="errors">
      {% for message in product.errors.full_messages() %}
        <li>{{ message }}</li>
      {% endfor %}
    </ul>
  {% endif %}

  <div>
    {{ form.label("name") }}
    {{ form.text_field("name") }}
  </div>
  <div>
    {{ form.label("description") }}
    {{ form.text_area("description") }}
  </div>
  {{ form.submit("Save product") }}
{% endcall %}
```

The underscore marks a reusable partial. `form_with(model=product)` chooses the
creation or update URL from the record's state, includes a CSRF token, and fills
fields from the model. Existing records use a hidden method override because
HTML forms only submit GET or POST directly.

Create `app/views/products/new.html`:

```html
{% extends "layouts/application.html" %}

{% block body %}
  <h1>New product</h1>
  {% include "products/_form.html" %}
  {{ link_to("Cancel", url_for("index_product")) }}
{% endblock %}
```

Create `app/views/products/edit.html`:

```html
{% extends "layouts/application.html" %}

{% block body %}
  <h1>Edit product</h1>
  {% include "products/_form.html" %}
  {{ link_to("Cancel", url_for("show_product", id=product.id)) }}
{% endblock %}
```

Both includes receive the current `product` variable.

### Accept only intended attributes

Our `_product_params()` method uses:

```python
return params.expect(product=["name", "description"])
```

This requires an outer `product` object and selects only the permitted fields.
It does not require every listed field to be present. Never pass unfiltered
request data to `create()` or `update()`; users could submit attributes that your
form does not expose.

### Handle validation failures

On success, `create` and `update` redirect to the product. On failure, they render
the form with status 422. Rendering keeps the invalid object, its errors, and
its entered values; redirecting would start a new request and lose that state.

Try these steps in your browser:

1. Create a product with a name and description.
2. Submit a new product with a blank name; check that the error and description remain.
3. Edit a product, blank its name, and check the same behavior.
4. Correct the name and save again.
5. Delete a product and confirm that it disappears from the list.

We now have a complete CRUD interface. The delete action above assumes the
model's default destruction behavior; if you later add callbacks that can reject
destruction, handle a `False` result explicitly.

### The scaffold shortcut

For future resources, a scaffold generates the model, migration, CRUD controller,
views, routes, fixtures, and tests together. For example, in a separate app:

```sh
bin/flask generate scaffold Post title:string content:text
bin/flask db:prepare
```

Do **not** generate a Product scaffold over this tutorial: generators may
replace files you have edited. Building it manually first makes the generated
code easier to understand and customize.

## 8. Test what you have built

Tests run against the `test` environment, not your development catalog.
`bin/flask test` prepares its database and runs pytest-based tests. Framework test
classes roll back their changes between tests.

### Model tests and fixtures

Create `test/fixtures/products.yml` (and its parent directory if needed):

```yaml
shirt:
  name: T-Shirt
  description: A comfortable cotton shirt.
```

Replace `test/models/product_test.py` with:

```python
from test.test_helper import ModelTest

from app.models.product import Product


class ProductTest(ModelTest):
    fixtures = ["products"]

    def test_save_persists_valid_product(self):
        product = Product.new(name="Socks", description="Warm socks.")

        assert product.save()
        assert Product.find(product.id).name == "Socks"

    def test_save_rejects_blank_name(self):
        product = Product.new(name="")

        assert not product.save()
        assert product.errors
        assert product.id is None

    def test_update_retains_invalid_input(self):
        product = self.products("shirt")

        assert not product.update(name="", description="Entered description.")
        assert product.name == ""
        assert product.description == "Entered description."
        assert product.errors
```

Fixture labels such as `shirt` avoid depending on a particular database ID.

### Request tests

Replace the generated `test/controllers/products_controller_test.py` with:

```python
from test.test_helper import IntegrationTest, get, post

from app.models.product import Product
from flaskteroids.routes import new_product_path, product_path, products_path


class ProductsControllerTest(IntegrationTest):
    def test_index_displays_catalog(self):
        get(products_path())

        self.assert_response("success")

    def test_create_persists_product(self):
        with self.assert_difference(Product.count):
            post(
                products_path(),
                params={"product": {"name": "Socks", "description": "Warm socks."}},
            )

        self.assert_redirected_to(product_path(Product.last()))

    def test_create_rejects_blank_name(self):
        with self.assert_difference(Product.count, by=0):
            post(products_path(), params={"product": {"name": ""}})

        self.assert_response(422)

    def test_new_displays_form(self):
        get(new_product_path())

        self.assert_response("success")
```

Run them:

```sh
bin/flask test
bin/flask test test/models/product_test.py
```

The request helpers simulate HTTP requests; they do not require a running
server. Browser tests are separate and use Playwright:

```sh
.venv/bin/playwright install chromium
bin/flask test:system
```

Our manually built resource has no browser tests yet; an empty system suite
succeeds. Scaffolds generate a starting browser test. See [Testing](testing.md)
for writing your own.

## 9. Require login to change products

Right now, anyone can create, edit, or delete products. Stop the server and run:

```sh
bin/flask generate authentication
bin/flask db:prepare
```

The generator adds `User` and `Session` models, login/logout and password-reset
controllers, templates, mailers, routes, and tests. It also adds an
`Authentication` concern to `ApplicationController`, making authentication the
default for its subclasses. There is no public sign-up form.

Open `bin/flask shell` and create your own account:

```python
from getpass import getpass

password = getpass("Choose a password: ")
user = User.create(
    email_address="you@example.org",
    password=password,
    password_confirmation=password,
)
assert not user.errors, user.errors.full_messages()
del password
exit()
```

`has_secure_password()` hashes the password; the database stores a digest, not
its plaintext. Use a real password of your own, and do not put it in source code.

Restart the server and visit <http://127.0.0.1:5000/products/new/>. You should be
redirected to the login page at `/session/new/`. Log in with your account.

### Keep the catalog public

Visitors should still be able to browse products without an account. In
`app/controllers/products_controller.py`, add `skip_before_action` to the
existing actions import:

```python
from flaskteroids.actions import before_action, skip_before_action
```

Replace the controller's `@rules(...)` declaration with:

```python
@rules(
    skip_before_action("_require_authentication", only=["index", "show"]),
    before_action("_set_authentication_status"),
    before_action("_set_product", only=["show", "edit", "update", "destroy"]),
)
```

Add this method inside `ProductsController`:

```python
    def _set_authentication_status(self):
        self.authenticated = self._is_authenticated()
```

`_require_authentication` and `_is_authenticated` are methods in the
application's generated authentication concern. The new callback exposes an
`authenticated` variable to our product templates, including public pages.

### Show login and logout controls

In `config/routes.py`, add
`route.post("/logout/", to="sessions#destroy", as_="logout")` inside the existing
`register(route)` function, keeping the authentication routes the generator added.
Use this dedicated POST endpoint for logout: standard HTML forms cannot send
DELETE directly, and the generated singular session resource shares its POST
path with login. This keeps logout working without custom JavaScript.

In `app/views/products/index.html`, replace the New product link with:

```html
{% if authenticated %}
  {{ link_to("New product", url_for("new_product")) }}
  {% call(form) form_with(url=url_for("logout")) %}
    {{ form.submit("Log out") }}
  {% endcall %}
{% else %}
  {{ link_to("Log in", url_for("new_session")) }}
{% endif %}
```

In `app/views/products/show.html`, wrap the Edit and Delete controls:

```html
{% if authenticated %}
  {{ link_to("Edit", url_for("edit_product", id=product.id)) }}
  {% call(form) form_with(url=url_for("destroy_product", id=product.id), method="DELETE") %}
    {{ form.submit("Delete") }}
  {% endcall %}
{% endif %}
```

Hiding controls is not access control: the controller callback protects the
write actions even if someone sends a request directly. This example has one
role: every account can manage the catalog. Ownership checks, permissions, and
public registration need additional application rules.

Log out and verify that browsing still works, while `/products/new/` requires
login again. Password reset also needs working mail delivery before real users
can rely on it.

### Update the request tests

The write actions now need authentication. Add these imports to
`test/controllers/products_controller_test.py`:

```python
from app.models.user import User
from flaskteroids.routes import new_session_path, session_path
```

Add a setup method inside the existing test class:

```python
    def setup(self):
        User.create(
            email_address="owner@example.org",
            password="test-password-only",
            password_confirmation="test-password-only",
        )
        post(
            session_path(),
            params={
                "email_address": "owner@example.org",
                "password": "test-password-only",
            },
        )
```

This uses the actual login endpoint rather than manufacturing a session cookie.
Add a separate class in the same file for guest access:

```python
class PublicProductsTest(IntegrationTest):
    def test_guest_can_browse_products(self):
        get(products_path())

        self.assert_response("success")

    def test_guest_is_redirected_to_login(self):
        get(new_product_path())

        self.assert_redirected_to(new_session_path())
```

Run `bin/flask test` again.

## 10. Upload product images

Install the attachment tables and configuration:

```sh
bin/flask attachments:install
bin/flask db:prepare
```

Stop and restart the server after this migration, as with other schema changes.

In `app/models/product.py`, import `has_one_attached` alongside `validates`, then
replace the model's rule declaration with:

```python
@rules(
    validates("name", presence=True),
    has_one_attached(
        "featured_image",
        max_size=2 * 1024 * 1024,
        content_types=["image/png", "image/jpeg"],
    ),
)
```

The attachment is not an extra column on `products`: the attachment tables keep
track of files and their owning records.

Inside the `form_with` block in `app/views/products/_form.html`, before the submit
button, add:

```html
<div>
  {{ form.label("featured_image") }}
  {{ form.file_field("featured_image", accept="image/png,image/jpeg") }}
</div>
```

`form_with` detects the file field and adds multipart encoding. Permit the upload
by replacing `_product_params()` in `ProductsController` with:

```python
    def _product_params(self):
        return params.expect(product=["name", "description", "featured_image"])
```

In the `body` block of `app/views/products/show.html`, add:

```html
{% if product.featured_image.attached() %}
  <img src="{{ blob_path(product.featured_image) }}" alt="{{ product.name }}">
{% endif %}
```

Log in, edit a product, and upload a small PNG or JPEG. After saving, its show
page should display the image. Files become available after the save commits.
An empty single-file input keeps the existing image.

Development uses local disk storage. Signed download links are accessible to
anyone who has the link by default, which suits public catalog images but not
private documents. Content-type checks are not file scanning. See
[Attachments](other/attachments.md) for storage services, authorization, request
size limits, and cleanup jobs.

## 11. Send product email

Mailers pair an action with HTML and plain-text templates. Let's create an email
that shares a product's details:

```sh
bin/flask generate mailer Product details
```

Replace `app/mailers/product_mailer.py` with:

```python
from app.mailers.application_mailer import ApplicationMailer
from app.models.product import Product


class ProductMailer(ApplicationMailer):
    def details(self, product_id, recipient):
        product = Product.find(product_id)
        self.product_name = product.name
        self.description = product.description
        return self.mail(to=recipient, subject=f"About {product.name}")
```

Replace `app/views/product_mailer/details.html` with:

```html
<h1>{{ product_name }}</h1>
<p>{{ description }}</p>
```

Replace `app/views/product_mailer/details.txt` with:

```text
{{ product_name }}

{{ description }}
```

The template variables are scalar values, so they can also be serialized when
we enqueue delivery. Do not put ORM objects or open files in background payloads.

### Test delivery without SMTP

Replace the generated `test/mailers/product_mailer_test.py` with:

```python
from test.test_helper import MailerTest

from app.mailers.product_mailer import ProductMailer


class ProductMailerTest(MailerTest):
    fixtures = ["products"]

    def test_delivers_product_details(self):
        product = self.products("shirt")

        with self.assert_emails(1):
            ProductMailer().details(product.id, "reader@example.org").deliver_now()

    def test_delivers_queued_product_details(self):
        product = self.products("shirt")

        with self.assert_emails(1), self.perform_enqueued_jobs():
            ProductMailer().details(product.id, "reader@example.org").deliver_later()
```

Run:

```sh
bin/flask test test/mailers/product_mailer_test.py
```

The test environment uses in-memory mail and queue adapters. These tests neither
contact an SMTP server nor require a Celery broker.

### Immediate versus background delivery

In an application context, such as `bin/flask shell`, delivery calls look like:

```python
from app.mailers.product_mailer import ProductMailer

product = Product.find_by(name="Socks")
ProductMailer().details(product.id, "reader@example.org").deliver_now()
```

Generated development configuration disables actual email delivery. The call
above does not send real mail until you configure SMTP and enable
`config.action_mailer.perform_deliveries` in your environment configuration.
Keep SMTP credentials out of source control; see [Configuration](configuration.md).

To enqueue delivery instead:

```python
ProductMailer().details(product.id, "reader@example.org").deliver_later()
```

**Outside tests, enqueuing requires a reachable Celery broker and a worker.**
Flaskteroids does not provision either service. Once a broker is configured,
start the worker from the application root in another terminal:

```sh
.venv/bin/celery -A jobs worker --loglevel=info
```

Both processes need matching broker configuration. Generated production settings
read `CELERY_BROKER_URL`; configure `config.active_job.broker_url` explicitly for
development if you want to try a local broker. Start the worker only after the
database is prepared. A disabled delivery setting remains disabled in the
worker, too.

This separates the HTTP response from delivery work. The same queue supports
application jobs with a `perform()` method; see [Background jobs](other/jobs.md)
and [Mailers](other/mailers.md). Attachment replacement/deletion may also enqueue
cleanup work, so deployed applications using uploads need a worker.

## 12. Add styles and understand assets

The generated layout already includes `app/assets/stylesheets/application.css`.
Replace or extend that file with:

```css
body {
  font-family: system-ui, sans-serif;
  max-width: 60rem;
  margin: 2rem auto;
  padding: 0 1rem;
}

form div {
  margin: 1rem 0;
}

label {
  display: block;
}

img {
  max-width: 100%;
  height: auto;
}

.errors {
  color: #b91c1c;
}
```

Refresh a product page to see the change. Development serves source assets
directly. Production uses fingerprinted files, built with:

```sh
bin/flask assets:precompile
```

Docker builds run this compilation automatically. Keep the generated output and
manifest together; production has no fallback to source files.

The generated layout also loads Turbo from a CDN. Flaskteroids' asset compiler
does not install import maps, bundle JavaScript, or compile Sass. See
[Assets](other/assets.md) when extending the frontend.

## 13. Security and continuous integration

Before deploying, run the complete suite:

```sh
bin/flask test
bin/flask test:system
```

The generated `.github/workflows/test.yml` provides a starting CI workflow.
Review it and keep your application's tests and browser dependencies up to date.
Linting or security scanners you choose for your application need their own
configuration.

Keep these boundaries in mind:

- Use `params.expect()` allowlists, even when the browser form looks harmless.
- Protect write actions on the server, not just their links in templates.
- Keep CSRF protection enabled; form helpers include the required tokens.
- Let Jinja and helpers escape user input. Never mark product descriptions safe
  merely to display formatting.
- Keep master keys, passwords, database URLs, and SMTP credentials out of Git.
- Do not expose the debug server to production traffic.
- Configure HTTPS, upload limits, access policies, and backups for your deployment.

## 14. Prepare for production

Flaskteroids generates a Dockerfile and deployment scripts. Start by reading
your app's `deploy/README.md`, which contains the commands matching your generated
application. You will need to choose and configure your own hosting platform.

For a local production-mode Docker check, commit your application lockfile and
build an image:

```sh
docker build -t store .
docker volume create store-storage
```

Supply `FLASKTEROIDS_MASTER_KEY` at runtime using your secret manager. For a local
check only, read the generated key into your shell and forward it to Docker:

```sh
export FLASKTEROIDS_MASTER_KEY="$(tr -d '\n' < config/master.key)"
docker run --rm -p 8000:8000 \
  --env FLASKTEROIDS_MASTER_KEY \
  --volume store-storage:/app/storage \
  store
```

Open <http://127.0.0.1:8000>. This is a **separate production database**, so it will
not contain the development products or account you created earlier. Stop the
container with `Ctrl-C` when finished and unset the key:

```sh
unset FLASKTEROIDS_MASTER_KEY
```

The default web startup prepares the production database before launching
Gunicorn. The volume keeps SQLite data and local uploads across container
restarts. The image runs unprivileged; host bind mounts must be writable by its
application user.

For a real deployment:

1. Provide the matching credentials key and environment settings through your
   hosting platform's secret management.
2. Configure your database and install its driver if using PostgreSQL or MySQL.
3. Coordinate migrations once per release when running multiple instances; do
   not use each web instance as migration coordination.
4. Configure mail, external storage if needed, and a Celery broker and worker.
5. Put the application behind HTTPS and arrange persistent storage and backups.
6. Create an initial user through an application shell in the production
   environment, using your host's execution facility and the account creation
   code from this guide. Do not add credentials to the image or Git.

See [Configuration](configuration.md#preparing-for-deployment) and your generated
deployment guide for release commands and service settings. The Docker check
above is not a complete internet-facing deployment recipe.

## 15. Where to go next

You have built a catalog with persistence, validation, HTML forms, authenticated
editing, image uploads, mail delivery, and tests.

Next, try expanding it:

- Add an inventory count using a new migration, a validation, a form field, and
  a permitted parameter.
- Add subscribers using `Subscriber` and `Product` associations, then send
  restock notifications through a mailer and background jobs.
- Add a browser test for a logged-in user creating and editing a product.
- Return JSON alongside HTML using controller content negotiation.

Explore the focused guides as you go:

- [Models](models/index.md): queries, transactions, associations, and callbacks.
- [Controllers](controllers/index.md) and [Routing](controllers/routing.md).
- [Views](views/index.md) and [Forms](other/forms.md).
- [Attachments](other/attachments.md), [Mailers](other/mailers.md), and
  [Background jobs](other/jobs.md).
- [Testing](testing.md), [Configuration](configuration.md), and
  [CLI](other/cli.md).
