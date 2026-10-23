# Views

Views are Jinja2 templates in `app/views`. By default, a controller action renders the template matching its controller and action name. For example, `PostsController.index` renders `app/views/posts/index.html`.

Controller instance variables become template variables. If the action sets `self.posts`, the template can use `posts`:

```html
<!-- app/views/posts/index.html -->
{% extends "layouts/application.html" %}

{% block body %}
<h1>Posts</h1>

<ul>
  {% for post in posts %}
  <li>{{ post.title }}</li>
  {% endfor %}
</ul>
{% endblock %}
```

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

`config.paths.helpers` defaults to the Python package `"app.helpers"`. Each
`*_helper.py` file must define its matching class: `products_helper.py` defines
`ProductsHelper`, and `admin/money_helper.py` defines `MoneyHelper`. Nested
directories can be namespace packages without `__init__.py`.

Only these conventional files are automatically imported. Private paths
(starting with `_`) are skipped. A missing helper package is allowed; syntax
errors, missing dependencies, and incorrectly named classes in existing helper
files stop application startup.

Helper classes act as mixins on a shared view context, not separately constructed
objects. Do not define `__init__`; initialize any render-local state lazily.
Public methods become callable template helpers. Private `_methods` remain
available to other helper methods through `self`, but are not exported to
templates.

Within a helper, `self` can access:
- Other included helper methods.
- Framework and route helpers, such as `self.link_to(...)` and
  `self.product_path(product)`.
- Explicitly exposed methods on the current controller or delivery-time mailer.
- Controller or mailer instance variables, such as `self.product`. Controller
  views can also use request facilities such as `self.params` and `self.request`.

Pass template-local values as arguments. Helpers do not become controller
methods or actions. Helper instance state is shared across the current view,
layout, and calls to `render(...)`, but does not survive a separate render or
request. Use `self.render(...)` to render a partial from another helper.

### Restricting automatic inclusion

To include shared application helpers and only conventionally matching
controller helpers, configure:

```python
config.action_controller.include_all_helpers = False
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

Conventional helpers are included before explicit declarations at each
controller level. Automatic inclusion of all helpers happens at the root
controller level in sorted helper-path order, with `ApplicationHelper` included
first. Later includes take precedence, but including an already-included class
does not move it.

A controller or mailer's `helper_method` declarations override helper mixins
included at that same level. A child's helper layer can override inherited
methods. Ordinary Python `super()` works between helper mixins. Application
helpers can override framework helpers; prefer unique names unless an override
is intentional.

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

The existing mail pipeline captures assigns rather than rerunning mailer actions
at delivery. One mailer instance is restored from those assigns per message,
without rerunning its constructor, actions, or callbacks. Its helper methods
share that instance across text and HTML parts. Queued assigns must satisfy the
queue adapter's serialization requirements. See [mailer helpers](../other/mailers.md#mailer-helper-methods).

Standalone Flask template rendering inside an application context uses all
application helpers by default, or just `ApplicationHelper` when
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

`link_to()` and `button_to()` escape ordinary text and HTML attribute values.
Use `markupsafe.Markup` only for HTML you trust, such as an application-defined
icon or label. Never mark user input safe. Attributes are escaped even when
supplied as `Markup`.

`link_to()` accepts relative URLs, including protocol-relative URLs, and the
`http`, `https`, `mailto`, and `tel` schemes. Form helpers accept relative and
HTTP(S) action URLs. Unsupported schemes, such as `javascript` and `data`, and
URLs containing control characters raise `ValueError`. HTML escaping alone does
not make an executable URL safe.

These checks do not restrict destination hosts. Applications must validate
user-supplied destinations when links or forms should stay on a particular site.
Keep HTML attribute names application-defined. Invalid names raise `ValueError`;
valid event-handler attributes still contain executable code and must never come
from untrusted input.
