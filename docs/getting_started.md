# Getting started with Flaskteroids

This guide walks you through building a small product catalog called `store`.
You will create records, display them in a browser, build forms, require login
for changes, and attach product images. Then you'll track stock and let visitors
subscribe to an email when a sold-out product becomes available again.

By the end, you will know how to:

- Create and run a Flaskteroids application.
- Work with models, migrations, and validations.
- Follow a request through routes, controllers, and views.
- Build a complete create, read, update, and delete (CRUD) interface.
- Add authentication, uploads, associations, and inventory tracking.
- Connect model callbacks to background restock emails and unsubscribe links.
- Test your application and prepare it for deployment.

You need basic Python and HTML knowledge, but no prior experience with Flask,
SQLAlchemy, or Celery. The examples introduce Flaskteroids APIs and conventions
as you build the application.

## 1. The Flaskteroids approach

Flaskteroids is a Python MVC framework built with Flask, SQLAlchemy, and Celery.
It gives these components a shared application structure and workflow.
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
bin/flask db:migrate
```

`db:migrate` applies pending migrations and regenerates `db/schema.py`. The
application generator already prepared the development database. The generated
database configuration uses `storage/development.sqlite3` for development and a
separate database for tests.

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

Before building pages, let's see what a product can do. Open the application
shell:

```sh
bin/flask shell
```

The shell provides an application context and makes your models available
automatically. You can use `Product` directly. In the examples below, `>>>` is
the Python prompt, not something to type; the lines without it show the result.

### Create and query

Build a product and save it:

```pycon
>>> product = Product.new(name="T-Shirt", description="A comfortable cotton shirt.")
>>> product.save()
True
>>> product.name
'T-Shirt'
```

`new()` builds an unsaved object. `save()` validates and persists it, returning
`True` on success. The database assigns `product.id` when the record is saved.
Create another product with the combined build-and-save operation:

```pycon
>>> pants = Product.create(name="Pants", description="Everyday trousers.")
>>> Product.count()
2
>>> [item.name for item in Product.all()]
['T-Shirt', 'Pants']
```

`create()` returns the object, including when validation fails. Later we will
use its errors to explain unsuccessful saves.

Find and filter records:

```pycon
>>> Product.find(product.id).name
'T-Shirt'
>>> Product.find_by(name="Pants").description
'Everyday trousers.'
>>> [item.name for item in Product.where(name="Pants").order(name="asc")]
['Pants']
```

`find()` raises `RecordNotFoundException` if the record is absent; `find_by()`
returns `None`. `all()` and `where()` return lazy queries: iteration loads the
records. Keep the returned query when chaining filters or ordering.

### Update and delete

Change the shirt's name, then try assigning and saving a description separately:

```pycon
>>> product.update(name="Cotton T-Shirt")
True
>>> product.description = "Available in several colors."
>>> product.save()
True
```

Assignments alone do not save a record. A standalone `save()`, `create()`,
`update()`, or `destroy()` commits before returning; no extra session or commit
call is needed. See [Models](models/index.md#assignment-validation-and-persistence)
when several operations need to succeed together.

Create a temporary product and delete it:

```pycon
>>> temporary = Product.create(name="Sample", description="For this example only.")
>>> temporary.destroy()
True
>>> Product.count()
2
```

The temporary record is gone, while our shirt and pants remain. We'll use those
products when we build the catalog page.

### Add validation

A product without a name would be hard to browse. Exit the shell with `exit()`,
then replace `app/models/product.py` with:

```python
from app.models.application_model import ApplicationModel
from flaskteroids.model import validates


class Product(ApplicationModel):
    validates("name", presence=True)
```

Declarations such as validations, associations, and callbacks go directly inside
the class body, with explicit imports. This validation requires a nonblank name.
It changes behavior, not database structure, so there is no migration to run.

Open a new `bin/flask shell` to load the edited model:

```pycon
>>> product = Product.new(name="", description="Still available for redisplay.")
>>> product.save()
False
>>> bool(product.errors)
True
>>> product.description
'Still available for redisplay.'
```

Run `product.errors.full_messages()` to read the validation messages. Notice that
the object still holds the entered description. That will let us redisplay a
form without making the visitor type everything again.

Fix the name and retry:

```pycon
>>> product.name = "Socks"
>>> product.save()
True
```

Exit with `exit()`. Your development database now has three products: Cotton
T-Shirt, Pants, and Socks. Next, let's give them a home on the web.

## 6. Follow a request through the application

Our product data exists, but it has no web interface yet. A page request follows
this path:

```text
GET /products
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
| GET | `/products` | `index` | List products. |
| GET | `/products/new` | `new` | Display a creation form. |
| POST | `/products` | `create` | Save a new product. |
| GET | `/products/<int:id>` | `show` | Display one product. |
| GET | `/products/<int:id>/edit` | `edit` | Display an editing form. |
| PUT/PATCH | `/products/<int:id>` | `update` | Save changes. |
| DELETE | `/products/<int:id>` | `destroy` | Delete a product. |

GET retrieves information. POST creates it, PUT/PATCH updates it, and DELETE
removes it. Helpers generate slashless resource URLs. A trailing slash is also
accepted without redirecting or replaying a request body.

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

The catalog lists product names, but visitors cannot open a product yet. We'll
add that first, then create products in the browser, edit them, and finally
remove them. Keep the existing controller actions as you add each new one.

### Show a product

In `app/controllers/products_controller.py`, add a `show` action:

```python
from app.controllers.application_controller import ApplicationController
from app.models.product import Product


class ProductsController(ApplicationController):
    def index(self):
        self.products = Product.all()

    def show(self):
        self.product = Product.find(self.params["id"])
```

The resource route captures the ID from `/products/<int:id>`. The `show` action
finds that product and makes it available to its template as `product`.

Create `app/views/products/show.html`:

```html
{% extends "layouts/application.html" %}

{% block body %}
  <h1>{{ product.name }}</h1>
  <p>{{ product.description }}</p>
  {{ link_to("Back", products_path()) }}
{% endblock %}
```

Now give visitors a way to reach it. In `app/views/products/index.html`, replace
`<li>{{ product.name }}</li>` with:

```html
<li>{{ link_to(product.name, product_path(product)) }}</li>
```

`link_to` builds a link. Resource helpers such as `product_path(product)`
have the same meaning in templates and Python; import them from
`flaskteroids.routes` in Python code. Native Flask `url_for` remains available
for custom endpoint-based routing.

**Try it:** refresh the catalog, click Cotton T-Shirt, and follow Back. You can
now browse both the collection and an individual product without typing its ID.

### Extract a presentation helper

Move reusable presentation logic into `app/helpers/products_helper.py`. If the
controller generator already created this file, replace its empty class:

```python
class ProductsHelper:
    def product_link(self, product):
        return self.link_to(product.name, self.product_path(product))
```

In `app/views/products/index.html`, the product list item can now be:

```html
<li>{{ product_link(product) }}</li>
```

Helper classes are loaded automatically: no controller import or callback is
needed. Inside a helper, `self` provides the shared view context, including
other helpers and route helpers. Ordinary strings are escaped; `link_to`
returns safely constructed HTML. See [application helpers](views/index.md#application-helpers)
for helper selection and inheritance.

### Create products in the browser

So far we have created products in the shell. A web form needs two actions:
`new` displays it, and `create` processes its submission.

Add this import to the controller:

```python
from flaskteroids.routes import product_path
```

Add these methods inside `ProductsController`, keeping `index` and `show`:

```python
    def new(self):
        self.product = Product.new()

    def create(self):
        self.product = Product.new(**self._product_params())
        if self.product.save():
            return self.redirect_to(product_path(self.product))
        return self.render("new", status=422)

    def _product_params(self):
        return self.params.expect(product=["name", "description"])
```

Create `app/views/products/new.html`:

```html
{% extends "layouts/application.html" %}

{% block body %}
  <h1>New product</h1>
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
  {{ link_to("Cancel", products_path()) }}
{% endblock %}
```

`form_with(model=product)` chooses the creation URL, includes a CSRF token, and
fills its inputs from the model. The generated field names put the submission
inside a `product` object.

Our `_product_params()` method uses `self.params.expect()` to require that outer
object and select only `name` and `description`. It does not require every
listed field to be present. Never pass unfiltered request data to a model:
visitors can submit attributes that your HTML form does not expose.

After the heading in `app/views/products/index.html`, add:

```html
{{ link_to("New product", new_product_path()) }}
```

**Try it:** click New product and create a product named Hat. You should land on
its show page. Follow Back and check that Hat appears in the catalog.

### Help visitors correct mistakes

Open New product again. Enter a description, leave the name blank, and save.
You should stay on the form, see a validation message, and keep your description.

That happens because `create` renders `new` with status 422 when saving fails.
Rendering reuses the invalid `product`, including its errors and entered values.
A redirect would start a new request and lose that state.

Enter a name and save again. The same form now succeeds. We have connected the
validation we tried in the shell to a useful browser experience.

### Edit an existing product

Editing has the same two-part shape: `edit` displays a form and `update` saves
its submission. Add these methods to `ProductsController`:

```python
    def edit(self):
        self.product = Product.find(self.params["id"])

    def update(self):
        self.product = Product.find(self.params["id"])
        if self.product.update(**self._product_params()):
            return self.redirect_to(product_path(self.product))
        return self.render("edit", status=422)
```

We could copy the creation form, but then every new field would need two edits.
Instead, move the complete `{% call(form) form_with(model=product) %}` block,
through its `{% endcall %}`, from `new.html` into a new file:
`app/views/products/_form.html`.

The underscore marks this as a reusable partial. Replace `new.html` with:

```html
{% extends "layouts/application.html" %}

{% block body %}
  <h1>New product</h1>
  {% include "products/_form.html" %}
  {{ link_to("Cancel", products_path()) }}
{% endblock %}
```

Create `app/views/products/edit.html`:

```html
{% extends "layouts/application.html" %}

{% block body %}
  <h1>Edit product</h1>
  {% include "products/_form.html" %}
  {{ link_to("Cancel", product_path(product)) }}
{% endblock %}
```

Both includes receive the current `product`. For a persisted record,
`form_with` chooses its member URL and PATCH. The helper renders a POST form
with a hidden PATCH override because browsers submit only GET or POST directly.
An explicit `method="PUT"` is supported, but PATCH is the inferred update method.

After the Back link in `app/views/products/show.html`, add:

```html
{{ link_to("Edit", edit_product_path(product)) }}
```

**Try it:** edit Hat, change its description, and save. Then try an edit with a
blank name. The editing form should retain your changes and explain the error,
just like the creation form. Correct the name before continuing.

### Extract the repeated lookup

`show`, `edit`, and `update` all start with the same product lookup. A
`before_action` lets us run it once before any of those actions.

In `app/controllers/products_controller.py`, add this import alongside the
existing imports:

```python
from flaskteroids.actions import before_action
```

Add the declaration **inside** `ProductsController`, before its existing methods:

```python
class ProductsController(ApplicationController):
    before_action("_set_product", only=["show", "edit", "update"])

    # Keep the existing actions and private methods here.
```

Replace `show`, `edit`, and `update` with these methods, and add `_set_product`:

```python
    def show(self):
        pass

    def edit(self):
        pass

    def update(self):
        if self.product.update(**self._product_params()):
            return self.redirect_to(product_path(self.product))
        return self.render("edit", status=422)

    def _set_product(self):
        self.product = Product.find(self.params["id"])
```

Keep `index`, `new`, `create`, and `_product_params` unchanged. Empty `show` and
`edit` actions still render their matching templates; the callback supplies the
record first.

**Try it:** visit a product and edit it again. The behavior should be identical;
we have removed duplication without changing the interface.

### Delete a product

We can browse, create, and edit. The last CRUD operation is deletion.

Add `products_path` to the existing route-helper import:

```python
from flaskteroids.routes import product_path, products_path
```

Add this action:

```python
    def destroy(self):
        self.product.destroy()
        return self.redirect_to(products_path(), status=303)
```

Update the existing `before_action` call inside `ProductsController` to include
`destroy`. Replace the call rather than adding a second one:

```python
    before_action("_set_product", only=["show", "edit", "update", "destroy"])
```

After the Edit link in `app/views/products/show.html`, add a deletion button:

```html
{{ button_to("Delete", product, method="DELETE") }}
```

This generates a POST form with a CSRF token and a hidden DELETE override.
Deleting data is a state-changing operation, not a GET link. The controller
redirects with status 303 so the browser retrieves the catalog afterward.

**Try it:** create a temporary product, delete it, and confirm that it disappears
from the catalog. Keep the original products for the next chapters.

You now have a complete CRUD interface. If you later add callbacks that can
reject destruction, handle a `False` result from `destroy()` explicitly.

### The scaffold shortcut

You have built the pieces yourself so you can understand and customize them.
For a future resource, a scaffold generates those pieces together. For example,
in a separate application:

```sh
bin/flask generate scaffold Post title:string content:text
bin/flask db:migrate
```

Do not generate a Product scaffold over this tutorial: generators may overwrite
your work. Next, let's decide who should be allowed to change the catalog.

## 8. Require login to change products

Right now, anyone can create, edit, or delete products. Stop the server and run:

```sh
bin/flask generate authentication
bin/flask db:migrate
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

Restart the server and visit <http://127.0.0.1:5000/products/new>. You should be
redirected to the login page at `/session/new`. Log in with your account.

### Keep the catalog public

Visitors should still be able to browse products without an account. In
`app/controllers/products_controller.py`, add `skip_before_action` to the
existing actions import:

```python
from flaskteroids.actions import before_action, skip_before_action
```

Replace the existing callback declaration inside `ProductsController` with
these two class-body calls, keeping its methods unchanged:

```python
    skip_before_action("_require_authentication", only=["index", "show"])
    before_action("_set_product", only=["show", "edit", "update", "destroy"])
```

The generated `Authentication` concern provides the `is_authenticated()` template
helper. It resumes the session when needed, including on public pages where
`_require_authentication` is skipped. No extra callback or controller variable
is needed.

### Show login and logout controls

Use the generated singular session resource for logout. Its `session_path()`
destination accepts POST for login and DELETE for logout; `button_to` renders
the browser-safe POST form, hidden DELETE override, and CSRF token. No extra
logout endpoint or JavaScript is needed.

In `app/views/products/index.html`, replace the New product link with:

```html
{% if is_authenticated() %}
  {{ link_to("New product", new_product_path()) }}
  {{ button_to("Log out", session_path(), method="DELETE") }}
{% else %}
  {{ link_to("Log in", new_session_path()) }}
{% endif %}
```

In `app/views/products/show.html`, wrap the Edit and Delete controls:

```html
{% if is_authenticated() %}
  {{ link_to("Edit", edit_product_path(product)) }}
  {{ button_to("Delete", product, method="DELETE") }}
{% endif %}
```

Hiding controls is not access control: the controller callback protects the
write actions even if someone sends a request directly. This example has one
role: every account can manage the catalog. Ownership checks, permissions, and
public registration need additional application rules.

Log out and verify that browsing still works, while `/products/new` requires
login again. Password reset also needs working mail delivery before real users
can rely on it.

**Checkpoint:** guests can browse the catalog, but only signed-in users can
create, edit, or delete products. Keep the account you created: we'll use it to
manage inventory shortly. We'll add automated checks after building the features.

## 9. Upload product images

A shopper can browse the catalog, but an image makes a product easier to
recognize. Let's add a photo without changing the product's ordinary edit flow.
Install the attachment tables and configuration:

```sh
bin/flask attachments:install
bin/flask db:migrate
```

Stop and restart the server after this migration, as with other schema changes.

In `app/models/product.py`, import `has_one_attached` alongside `validates`, then
update the declarations inside `Product` to:

```python
    validates("name", presence=True)
    has_one_attached(
        "featured_image",
        max_size=2 * 1024 * 1024,
        content_types=["image/png", "image/jpeg"],
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
        return self.params.expect(product=["name", "description", "featured_image"])
```

In the `body` block of `app/views/products/show.html`, add:

```html
{% if product.featured_image.attached() %}
  <img src="{{ blob_path(product.featured_image) }}" alt="{{ product.name }}">
{% endif %}
```

Log in, edit a product, and upload a small PNG or JPEG. After saving, its show
page should display the image. Reopen Edit and save without selecting another
file: the existing image should remain. Files become available after the save
commits.

Development uses local disk storage. Signed download links are accessible to
anyone who has the link by default, which suits public catalog images but not
private documents. Content-type checks are not file scanning. See
[Attachments](other/attachments.md) for storage services, authorization, request
size limits, and cleanup jobs.

## 10. Notify visitors when products return to stock

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
{% extends "layouts/application.html" %}

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
    route.get("/unsubscribe/<token>/", to="unsubscribes#show", as_="unsubscribe")
    route.post(
        "/unsubscribe/<token>/", to="unsubscribes#destroy", as_="cancel_subscription"
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
{% extends "layouts/application.html" %}

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

`with_(...)` supplies the mailer's `self.params`, using the same API as
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
    config.action_controller.perform_caching = False
    config.attachments.service = "local"
    config["SERVER_NAME"] = "127.0.0.1:5000"
    config.action_mailer.perform_deliveries = True
    config.action_mailer.delivery_method = ConsoleDeliveryMethod
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
ProductMailer.with_(
    product=product, subscriber=subscriber
).in_stock().deliver_now()
```

You should see a readable message preview in the shell, with a subject ending
in "is back in stock", a product link, and an unsubscribe link. Exit the shell.
The action runs immediately; `deliver_later()` queues its captured template
assigns, not `self.params`. See [Mailers](other/mailers.md) for delivery details.

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
    after_commit("_notify_subscribers", on="update", if_="_back_in_stock")

    def _back_in_stock(self):
        change = self.saved_change_to_attribute("inventory_count")
        return change is not None and change[0] == 0 and change[1] > 0

    def _notify_subscribers(self):
        for subscriber in self.subscribers:
            ProductMailer.with_(
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
[Models](models/index.md) for callbacks, saved changes, and transactions.

### Watch the complete feature work

Restart the web server to load the model. From `store`, start a worker in another
terminal:

```sh
.venv/bin/celery -A jobs worker --loglevel=info
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
`CELERY_BROKER_URL`. See [Mailers](other/mailers.md), [Background jobs](other/jobs.md),
and [Configuration](configuration.md) for those settings.

## 11. Give the store a little polish

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

## 12. Test the store's behavior

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
            ProductMailer.with_(
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

        self.fill_in("Name", with_="Browser hat")
        self.fill_in("Description", with_="A hat created in the browser.")
        self.click_on("Save product")
        self.assert_selector("h1", text="Browser hat")

        self.click_on("Edit")
        self.fill_in("Name", with_="Updated browser hat")
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
subscribing and delivering its restock email. See [Testing](testing.md) for
uploads, additional assertions, and running selected tests in parallel.

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

- Use `self.params.expect()` allowlists, even when the browser form looks harmless.
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
4. Configure SMTP and a sender address for real mail, your canonical host via
   `SERVER_NAME` for email links, external storage if needed, and a Celery broker
   and worker. The tutorial's console adapter is only enabled in development.
5. Put the application behind HTTPS and arrange persistent storage and backups.
6. Create an initial user through an application shell in the production
   environment, using your host's execution facility and the account creation
   code from this guide. Do not add credentials to the image or Git.

See [Configuration](configuration.md#preparing-for-deployment) and your generated
deployment guide for release commands and service settings. The Docker check
above is not a complete internet-facing deployment recipe.

## 15. Where to go next

You started with an empty application and built a working store: visitors browse
products, owners manage stock and images, and subscribers hear when a product
returns. Tests now check the behavior that makes those features work together.

Next, try expanding it:

- Add product categories with another model and association.
- Add pagination and filtering to the catalog.
- Confirm subscription addresses before enabling notifications for real visitors.
- Write a browser test for the complete subscribe-and-unsubscribe journey.
- Return JSON alongside HTML using controller content negotiation.

Explore the focused guides as you go:

- [Models](models/index.md): queries, transactions, associations, and callbacks.
- [Controllers](controllers/index.md) and [Routing](controllers/routing.md).
- [Views](views/index.md) and [Forms](other/forms.md).
- [Attachments](other/attachments.md), [Mailers](other/mailers.md), and
  [Background jobs](other/jobs.md).
- [Testing](testing.md), [Configuration](configuration.md), and
  [CLI](other/cli.md).
