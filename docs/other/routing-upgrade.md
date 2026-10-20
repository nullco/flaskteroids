# Adopting conventional resource routes and forms

These changes affect existing applications when upgrading the framework. New
generators use the supported flow; they do **not** rewrite installed application
files. Review customized controllers, templates, routes, mailers, and tests before
deploying. Do not regenerate authentication or scaffolds over application edits.

## Resource URLs and helper names

Helpers now generate `/products`, `/products/1`, and `/products/1.json`. Optional
trailing slashes remain accepted directly: `/products/1/` and `/products/1.json/`
reach the same action without a redirect, method conversion, or body replay.
Individual manually declared paths retain their declared spelling. Unsupported
methods on framework-managed paths now return 404, not Flask's automatic 405.
Unrelated native Flask endpoints retain their existing behavior.

Use collection/member helpers instead of action-specific resource helper names:

```python
products_path()                        # index or create destination
product_path(product)                  # show, update, or destroy destination
new_product_path()
edit_product_path(product)
product_subscriber_path(product, subscriber)
```

Each has an `_url` counterpart. Templates expose these same helpers; update
scaffold links and redirects as convenient. Native Flask `url_for` remains an
advanced escape hatch; internal action endpoint names still exist, but are not
the resource helper API. Conflicting endpoint/helper/template-global names now
fail clearly rather than silently replacing another binding.

Nesting no longer renames a parent's own member parameter: products still receive
`id`, while their children receive `product_id`. Custom `param="slug"` supplies
`slug` on the parent and `product_slug` on children. Review controller lookups
that previously compensated for the incorrect parent binding.

Forms now infer destinations from declared route metadata rather than guessing
create/update endpoint names. For manually declared routes, declare conventional
named helpers with `as_` or supply an explicit form URL; prefer `resources` for
ordinary CRUD. Raw native Flask apps can still use model data with explicit URLs.

For custom identifiers, use explicit helper arguments or override `to_param()`
intentionally. Its default is the persisted record's ID, not an arbitrary
attribute guessed from the route parameter name. Missing ancestor/member
identities fail rather than falling back to current request values.

## Form and button defaults

Persisted model forms now infer **PATCH**, not PUT. Explicit `method="PUT"`
continues to work. Explicit URLs are honored without losing model field data,
errors, before-type-cast input, or default persistence-state method inference:

```html
{% call(form) form_with(model=product, url="/review", method="POST") %}
  {{ form.text_field("name") }}
  {{ form.submit("Review") }}
{% endcall %}
```

Here POST is explicit because a persisted `product` would otherwise infer PATCH.
URL omission/None permits inference, `url=False` omits `action`, and `url=""`
keeps an explicit empty action. GET forms no longer include CSRF tokens or
method overrides; reload old rendered forms rather than sharing token-bearing
HTML between sessions.

Update the old positional button method to a keyword:

```html
{{ button_to("Delete", product, method="DELETE") }}
{{ button_to("Log out", session_path(), method="DELETE") }}
```

Buttons accept URLs, records, or nested model lists/tuples. Defaults are POST for
URLs/new records and PATCH for persisted records; deletion is always explicit.
Put form attributes in `form={...}` and button attributes in the ordinary keyword
arguments. Unsupported/executable URL schemes remain rejected.

## Authentication and nested forms

Keep the generated session resource; no extra POST logout endpoint is necessary:

```python
route.resource("session", only=["new", "create", "destroy"])
```

Use the explicit DELETE button above, then remove an application-owned logout
workaround after verifying login/logout with CSRF enabled. Existing generated
concerns/controllers are not overwritten and authentication policy is unchanged.
The generator also limits password routes to their implemented actions.

Replace manually assembled child routes and field names with ordinary nesting:

```python
route.resources("products", nested=lambda child: child.resources("subscribers"))
```

```html
{% call(form) form_with(model=[product, subscriber]) %}
  {{ form.email_field("email") }}
  {{ form.submit("Subscribe") }}
{% endcall %}
```

The child supplies fields/persistence state; the parent supplies the ancestor
binding. Use `scope=` only for an intentional field-name override. Controllers
must still allowlist input with `params.expect`; this does not enable automatic
nested-attribute persistence.

## Override and parsing boundaries

Override handling applies only to original POST requests on framework-managed
paths. A native endpoint that matches the original method at a shared path keeps
its dispatch. `_method` form data wins over the override header, including empty
or unsupported values that block fallback. Query strings cannot override the
method. Repeated scalar values use the last value. Unsupported overrides retain
POST; a recognized verb without a route never retries create.

Both `request.form` and framework `params` now retain `_method`. It is transport
metadata, not an attribute to mass-assign. CSRF tokens remain filtered from
`params`. Early normalization uses the same request and dependency parser, retains
uploads, and checks CSRF against the effective operation. Malformed eligible POST
forms are rejected with 400. Configure parsing limits on the application (or an
early request customization), not in an action after parsing has already occurred.

Review callbacks or extensions that inspected `request.method`: it is now the
effective method rather than POST for an overridden request. Native endpoints
outside framework-managed routing do not acquire override behavior incidentally.
