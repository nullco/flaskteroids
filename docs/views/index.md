# Views

Views are Jinja templates in `app/views`. They turn the data prepared by a
controller into HTML.

After reading this guide, you will know how to:

- Render a page and extract reusable partials.
- Share presentation logic through helper classes.
- Keep template output escaped.

## Render a page

By default, controller and action names choose the template.
`PostsController.index` renders `app/views/posts/index.html`. Values assigned
by the action become template variables, so `self.posts` is available as
`posts`.

```html
<!-- app/views/posts/index.html -->
{% extends layout %}

{% block body %}
<h1>Posts</h1>

<ul>
  {% for post in posts %}
  <li>{{ post.title }}</li>
  {% endfor %}
</ul>
{% endblock %}
```

## Render a partial

A partial is a template you can reuse inside another template. Put a post's
display markup in `app/views/posts/_post.html`:

```html
<article>
  <h2>{{ post.title }}</h2>
</article>
```

Render it with a local value:

```html
{{ render(partial="posts/post", locals={"post": post}) }}
```

With conventional names, `{{ render(post) }}` selects the same partial and
supplies `post` automatically. The template helper returns HTML; it is different
from a controller's `self.render(...)`, which prepares an HTTP response.

## Turbo Frames and Streams

Use [Turbo Frames and Streams](turbo.md) to navigate within a page or update
several elements after a form submission. Page templates use
`{% extends layout %}` so the controller can select a full-page or frame layout.

## Translations and dates

Use `t("products.index.title")` for translations and `l(value, format="short")`
for localized dates and times. A relative key such as `t(".title")` uses the
current template context. See [Internationalization](../other/internationalization.md)
for YAML catalogs, locale selection, pluralization, and safe HTML translations.

## Application helpers

Put reusable presentation methods in helper classes under `app/helpers`. The
application generator creates `ApplicationHelper`; the controller generator
also creates a matching helper class.

For example:

```python
# app/helpers/products_helper.py
class ProductsHelper:
    def product_link(self, product):
        return self.link_to(product.name, self.product_path(product))
```

Use it directly in a view, layout, or partial:

```html
{{ product_link(product) }}
```

By default, all conventional helper classes are available in every controller's
views. No import, callback, or `helper_method` declaration is needed.

### Discovery and the view context

Helper files follow a naming convention: `products_helper.py` defines
`ProductsHelper`. Put shared methods in `ApplicationHelper`. All conventional
helper classes are included in controller views by default.

A helper runs on a **view context**, not the controller. Within a helper, use
`self` to call other helpers, route helpers, or explicitly exposed controller
methods. Pass template-local values as arguments.

Public methods are available in templates; underscore-prefixed methods remain
private to helpers. Do not define `__init__`. Any state you create is shared by
the current view, layout, and partials, but not by separate renders or requests.

### Restricting automatic inclusion

To include shared application helpers and only conventionally matching
controller helpers, configure:

```python
config.controller.include_all_helpers = False
```

For example, `ProductsController` receives `ApplicationHelper` and
`ProductsHelper`. Child controllers inherit their parents' helper selections
and add their own matching helper. Namespaced controllers match namespaced
helper paths.

Include other helper classes explicitly inside the controller class:

```python
from app.controllers.application_controller import ApplicationController
from app.helpers.formatting_helper import FormattingHelper
from flaskteroids.controller import helper


class ProductsController(ApplicationController):
    helper(FormattingHelper, "admin/money")
```

Names such as `"formatting"`, `"FormattingHelper"`, and `"admin/money"` resolve
against the configured helper package. `helper("all")` explicitly includes all
discovered helpers.

`helper(...)` includes presentation helpers in the view context;
[`helper_method(...)`](../controllers/index.md#controller-helpers)
delegates a particular method to the current controller or delivery-time mailer.

### Method precedence

Prefer unique helper method names. When names overlap, later includes override
earlier ones, and a child controller's helpers can override inherited helpers.
Use ordinary Python `super()` when extending an inherited helper method.

### Mailers and rendering outside requests

Mailer templates do not inherit the current request controller's helper methods
or automatically include every application helper. Include the classes they
need explicitly:

```python
from app.mailers.application_mailer import ApplicationMailer
from flaskteroids.mailer import helper


class NoticesMailer(ApplicationMailer):
    helper("application", "formatting")
    # Mailer actions go here.
```

A conventionally matching `NoticesMailerHelper`, if defined in
`notices_mailer_helper.py`, is also included. Mailer instance variables are
available to helpers through `self`. These selections apply to immediate and
queued delivery. Mailers can also expose their own private methods with
`helper_method`, imported from `flaskteroids.mailer`. These declarations are
inherited, honor overridden methods, and accept arguments just like controller
helper methods. They delegate to the mailer, never to a request controller.

See [Mailers](../other/mailers.md) for delivery-time values and helper methods.

### Rendering without a controller

Flask template rendering inside an application context uses all application
helpers by default, or just `ApplicationHelper` when
`include_all_helpers` is false. Controller delegates are unavailable without
a current request controller. Request-dependent helpers still require a request;
URL generation outside a request follows Flask's normal configuration rules.
Jinja macros imported without context do not receive render-local helpers;
import them `with context` when needed.

### Development changes

Helper modules are imported at application boot. Use `bin/flask run --debug`
for Flask's process reloader, or restart the server after changing Python
helpers. The framework does not perform a separate in-process module reload.
`config.enable_reloading` enables template reloading but does not, by itself,
reload Python helper code.

## Helper escaping and URLs

Template output is HTML-escaped by default. Keep that protection when writing
helpers: `link_to()` and `button_to()` escape ordinary text and attribute values.
Use `markupsafe.Markup` only for HTML you trust, such as an application-defined
icon or label. Never mark user input safe. Attributes are escaped even when
supplied as `Markup`.

`link_to()` accepts relative URLs, including protocol-relative URLs, and the
`http`, `https`, `mailto`, and `tel` schemes. Form helpers accept relative and
HTTP(S) action URLs. Unsupported schemes, such as `javascript` and `data`, and
URLs containing control characters raise `ValueError`. HTML escaping alone does
not make an executable URL safe.

`link_to`, `button_to`, `form_with`, and Turbo tag helpers accept `class_="button"`
as `class="button"`, nested `data={"turbo_frame": "editor"}` /
`aria={"label": "Edit"}` dictionaries, and
boolean HTML attributes. For example, `disabled=True` includes the boolean
attribute; `False` omits it. Data/ARIA booleans instead emit `"true"` or `"false"`.

These checks do not restrict destination hosts. Applications must validate
user-supplied destinations when links or forms should stay on a particular site.
Keep HTML attribute names application-defined. Invalid names raise `ValueError`;
valid event-handler attributes still contain executable code and must never come
from untrusted input.
