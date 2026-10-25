# Routing

Routes connect URLs and HTTP methods to controller actions. Define them in
`config/routes.py`, inside its `register(route)` function.

A destination such as `"products#show"` means: call `show` on
`ProductsController` in `app/controllers/products_controller.py`.

## Individual routes

```python
def register(route):
    route.root(to="products#index")
    route.get("/about", to="pages#about", as_="about")
    route.post("/login", to="sessions#create")
    route.put("/products/<int:id>", to="products#update")
    route.patch("/products/<int:id>", to="products#update")
    route.delete("/products/<int:id>", to="products#destroy")
```

`<int:id>` captures an integer from the URL and makes it available as
`self.params["id"]`. Other bindings use Flask/Werkzeug's converter syntax.

The root route controls `/`. If you omit it, Flaskteroids shows its welcome page.
Individual routes keep the trailing-slash spelling you declare.

## Resources

Use `resources` for the standard create, read, update, and delete actions:

```python
def register(route):
    route.resources("products")
```

| Method | Path | Action | Public path helper |
| --- | --- | --- | --- |
| GET | `/products` | index | `products_path()` |
| POST | `/products` | create | `products_path()` |
| GET | `/products/new` | new | `new_product_path()` |
| GET | `/products/<int:id>` | show | `product_path(product)` |
| GET | `/products/<int:id>/edit` | edit | `edit_product_path(product)` |
| PUT/PATCH | `/products/<int:id>` | update | `product_path(product)` |
| DELETE | `/products/<int:id>` | destroy | `product_path(product)` |

A **collection** URL addresses all products; a **member** URL addresses one.
Several actions share a path: the HTTP method selects which action runs. For
example, GET `/products` lists products, while POST `/products` creates one.

Resource helpers generate paths **without trailing slashes**. Requests with or
without a trailing slash reach the same action, including `.json/` and
`.turbo_stream/` requests.

Limit actions with `only`; an empty list generates no resource actions:

```python
route.resources("products", only=["create", "update", "destroy"])
```

Collection and member helpers remain available even if you exclude index/show.
Unsupported HTTP methods on framework routes return 404; they do not run another
action as a fallback.

### Uncountable resources

Uncountable names distinguish collection and member helpers with `_index`:

```python
route.resources("fish")

fish_index_path()  # /fish
fish_path(fish)    # /fish/1
new_fish_path()    # /fish/new
```

Model-backed forms and buttons use these same names, including nested resources.

### Singular resources

A singular resource has no member ID:

```python
route.resource("session", only=["new", "create", "destroy"])
```

This provides `new_session_path()` at `/session/new` and `session_path()` at
`/session`. POST creates a session; DELETE destroys it. The controller remains
plural: `SessionsController`. A default singular resource additionally provides
show, edit, and PUT/PATCH update, but never index.

### Nested resources

Nest a resource when its URL should include a parent, such as a product's
subscribers:

```python
route.resources(
    "products",
    nested=lambda child: child.resources("subscribers"),
)
```

The parent's own member routes still receive `id`. A subscriber collection
receives `product_id`; a subscriber member receives both `product_id` and its own
`id`.

```python
products_path()                              # /products
product_path(product)                        # /products/1
product_subscribers_path(product)            # /products/1/subscribers
product_subscriber_path(product, subscriber) # /products/1/subscribers/2
new_product_subscriber_path(product)         # /products/1/subscribers/new
edit_product_subscriber_path(product, subscriber)
# /products/1/subscribers/2/edit
```

Deeper nesting keeps every ancestor's identifier. To declare several child
resources, unpack their returned route lists:

```python
route.resources("products", nested=lambda child: [
    *child.resources("subscribers"),
    *child.resources("reviews"),
])
```

### Custom parameters

```python
route.resources(
    "products", param="slug",
    nested=lambda child: child.resources("subscribers"),
)
```

The parent receives `slug`; the child receives `product_slug` plus its own `id`.
`param="int:sku"` instead supplies integer `sku` and `product_sku` bindings.
Path bindings take precedence over query parameters and form fields.
Setting `param="slug"` changes the URL parameter name; it does not tell helpers
to read `product.slug`. Pass the slug explicitly, or override `to_param()`:

```python
product_path("cotton-shirt")
product_subscriber_path(product_slug="cotton-shirt", id=2)

class Product(ApplicationModel):
    def to_param(self):
        return self.slug if self.is_persisted() else None
```

The default `to_param()` returns a persisted record's ID as a string; unsaved
records have no member identity. Model-backed forms/buttons for new records use
collection destinations instead.

## Helpers in Python and templates

```python
from flaskteroids.routes import product_path, product_url

product_path(product)               # /products/1
product_path(id=1, page=2)           # /products/1?page=2
product_url(product)                # https://example.test/products/1
```

The same helpers are available directly in Jinja:

```html
{{ link_to(product.name, product_path(product)) }}
```

Every `_path` helper has a `_url` counterpart that includes the scheme and host.
Helpers use the active application's routes and deployment prefix. They do not
query records or fill missing parameters from the current request.

- Missing parameters raise `ValueError`.
- Extra positional arguments or duplicate parameters raise `TypeError`.
- Ambiguous route/helper names or collisions with template globals are
  configuration errors.

Outside a request, use an application context and configure Flask's `SERVER_NAME`
and, where needed, `APPLICATION_ROOT` and `PREFERRED_URL_SCHEME`. Explicit callers
control query values; do not forward unfiltered request parameters to URL helpers.
Native Flask `url_for` remains available for advanced endpoint-based routing.

An individual route's `as_` declares its public helper name:

```python
route.get("/dashboard", to="products#index", as_="dashboard")
# dashboard_path(), dashboard_url()
```

## Response formats

Use resource format suffixes, not separate action helpers:

```python
products_path(format="json")        # /products.json
product_path(product, format="json") # /products/1.json
products_path(format="turbo_stream") # /products.turbo_stream
product_path(product, format="turbo_stream") # /products/1.turbo_stream
```

These URLs call the same actions as the HTML paths. Use
[`self.respond_to(...)`](index.md#content-negotiation) in the controller to choose
an HTML, JSON, or Turbo Stream response. Explicit `.json` and `.turbo_stream`
suffixes override `Accept` negotiation; `.turbo_stream` forces a Stream response,
not HTML fallback. Without a suffix, Turbo forms can negotiate Streams or fall
back to acceptable HTML. See [Turbo Streams](../views/turbo.md#negotiation-and-routes).

Suffix support belongs to resource routes. Existing custom named routes do not
automatically gain `.json` or `.turbo_stream` variants.

## HTML method overrides

Browsers submit GET or POST forms. [`form_with` and `button_to`](../other/forms.md)
render PUT/PATCH/DELETE as POST plus a hidden `_method` and a CSRF token:

```html
{{ button_to("Log out", session_path(), method="DELETE") }}
```

Use the helpers rather than building hidden fields yourself. An overridden
DELETE has the same routing and CSRF protection as an actual DELETE request.
Overrides apply to all routes in the application, including native Flask routes;
`request.method` reports the effective method.

For manual requests:

- Only POST can be overridden.
- The `_method` form field takes precedence over `X-HTTP-Method-Override`.
- Query parameters cannot change the method.
- An unsupported override leaves the request as POST.
