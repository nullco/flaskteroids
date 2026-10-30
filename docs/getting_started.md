# Getting started with Flaskteroids

Welcome! In this guide, you will build a small product catalog called `store`.
You will create products, display them in a browser, and build forms to add,
edit, and delete them.

After working through this guide, you will know how to:

- Create and run a Flaskteroids application.
- Define a model, migrate its table, and validate input.
- Follow a request through routes, controllers, and views.
- Build a create, read, update, and delete (CRUD) interface.

You need basic Python and HTML knowledge, but no experience with Flask,
SQLAlchemy, or Celery.

## About the store tutorial

This guide is the first part of a tutorial. You can stop with a working catalog,
or continue to build a fuller store, one feature at a time:

1. **Getting started** — build the product catalog on this page.
2. [Add login and product images](tutorial/authentication_and_uploads.md).
3. [Add restock notifications](tutorial/restock_notifications.md).
4. [Test the store](tutorial/testing.md).
5. [Prepare the store for deployment](tutorial/deployment.md).

Each part continues in the same application. The
[component guides](index.md#find-a-guide) explain individual features when you
want to explore them without following the whole tutorial.

## The Flaskteroids approach

Flaskteroids is a Python MVC framework built with Flask, SQLAlchemy, and Celery.
It gives these components a shared application structure and workflow.
Two ideas guide that workflow:

- **Convention over configuration:** names and directories tell the framework
  where your models, controllers, templates, and jobs belong.
- **Don't repeat yourself:** migrations describe database structure; models
  describe behavior; reusable templates and callbacks keep shared logic together.

You can use the underlying libraries when needed, but ordinary application work
should not require managing ORM mappings or database sessions yourself.

## Create your application

### Prerequisites

Install these tools before continuing:

- Python 3.14 or newer.
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
flask new store
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

If you used `flask new store --skip-install`, run `bin/setup` before
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

## Hello, Flaskteroids!

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

## Create a product model

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

## Work with records in the shell

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

## Follow a request through the application

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
{% extends layout %}

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
`{% extends layout %}` uses the framework-provided `layout` variable: normally
`layouts/application.html`, or a minimal layout for Turbo Frame requests. Use
this in page templates so they respect controller layout overrides and
[frame-aware layout selection](views/turbo.md#frames-and-layouts).

Run `bin/flask run --debug` again and visit <http://127.0.0.1:5000>. You should see
the products you created in the shell.

## Build the CRUD interface

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
{% extends layout %}

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
{% extends layout %}

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
{% extends layout %}

{% block body %}
  <h1>New product</h1>
  {% include "products/_form.html" %}
  {{ link_to("Cancel", products_path()) }}
{% endblock %}
```

Create `app/views/products/edit.html`:

```html
{% extends layout %}

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
from the catalog. Keep the original products if you continue the tutorial.

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
your work.

## Next steps

You have built a working catalog: visitors can browse products, create them,
correct invalid input, edit details, and delete records.

Continue with [Add login and product images](tutorial/authentication_and_uploads.md)
to decide who can change the catalog. Or explore [Models](models/index.md),
[Routing](controllers/routing.md), and [Forms](other/forms.md) to learn more about
the pieces you have used.
