# Routing

Define routes in `config/routes.py`. Its `register` function receives a router.
Actions use `"controller#action"`: `products#show` calls
`ProductsController.show` from `app/controllers`.

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

Use Flask/Werkzeug converter syntax for typed bindings. A root route is optional;
without one, Flaskteroids displays its welcome page. Explicit individual paths
keep the slash spelling you declare.

## Resources

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

Collection and member helpers name destinations, not individual actions. HTTP
methods distinguish create from index, and update/destroy from show. Resource
paths are generated **without trailing slashes**. Requests with or without a
trailing slash reach the same action, including `.json/` requests.

Limit actions with `only`; an empty list generates no resource actions:

```python
route.resources("products", only=["create", "update", "destroy"])
```

The collection/member helpers remain available without index/show. Unsupported
operations on framework routes return 404; they do not fall back to another verb.

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

Multiple levels retain each ancestor's identity. To declare siblings, concatenate
or unpack the returned route lists:

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
Changing a route parameter does not guess an attribute on a model. Pass explicit
identifiers or intentionally override the model's public `to_param()`:

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

Every `_path` helper has an absolute `_url` counterpart. Helpers resolve against
the active application, including its script prefix; they do not query records
or obtain missing bindings from the current request. Missing bindings raise
`ValueError`; extra positional or duplicate bindings raise `TypeError`. Ambiguous
route/helper declarations and template-global collisions are configuration errors.

Outside a request, use an application context and configure Flask's `SERVER_NAME`
and, where needed, `APPLICATION_ROOT` and `PREFERRED_URL_SCHEME`. Explicit callers
control query values; do not forward unfiltered request parameters to URL helpers.
Native Flask `url_for` remains available for advanced endpoint-based routing.

An individual route's `as_` declares its public helper name:

```python
route.get("/dashboard", to="products#index", as_="dashboard")
# dashboard_path(), dashboard_url()
```

## JSON destinations

Use format suffixes, not separate action helpers:

```python
products_path(format="json")        # /products.json
product_path(product, format="json") # /products/1.json
```

CRUD actions dispatch to the same controller actions as their HTML paths. A
controller's `respond` selects JSON from a `.json` suffix or the Accept header.
Only JSON format generation is currently supported.

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

For manual requests, only POST can be overridden. The `_method` form field takes
precedence over `X-HTTP-Method-Override`; query parameters cannot change the method.
Unsupported values leave the request as POST.
