# Controllers

Controllers handle HTTP requests. Each action is a public method on a controller
class. Actions load or change model data, then render a page, return JSON, or
redirect the browser.

## Write an action

If an action does not prepare a response, Flaskteroids renders its matching
template. Instance variables become template variables:

```python
# app/controllers/posts_controller.py
from app.models.post import Post
from flaskteroids.controller import ActionController


class PostsController(ActionController):
    def index(self):
        self.posts = Post.all()

    def show(self):
        self.post = Post.find(self.params["id"])
```

`index` renders `app/views/posts/index.html`, where `posts` is available.
`show` renders `app/views/posts/show.html`, where `post` is available.
Native Flask response return values, including empty strings and dictionaries,
are also supported.

Read request input from `self.params`. Templates can access the same mapping as
`params`. Before passing input to a model, filter it with
[`self.params.expect(...)`](../other/forms.md#strong-parameters).

## Rendering responses

Use `render` when you need to choose the template, response format, or status:

```python
return self.render("new", status=422)
return self.render(json={"message": "Saved"}, status=200)
```

`self.render()` without a template name selects the current action. Status values
can be integers or `HTTPStatus` members.

**Rendering prepares a response; it does not stop Python execution.** Use
`return self.render(...)` to exit the action. Preparing another response raises
`DoubleRenderError` from `flaskteroids.exceptions`.

The template/helper function `render(...)` is different: it renders a partial,
not a controller response.

### JSON values

JSON rendering accepts dictionaries, lists, strings, numbers, booleans, and
`None`. Empty values remain empty JSON values; `None` becomes `null`, and tuples
become arrays.

Models, queries, and other objects with a callable `__json__()` use that method,
even when nested in containers. Its result is processed recursively. Other types
are passed to Flask's JSON provider, including custom serialization:

```python
return self.render(json={"posts": Post.all(), "featured": post})
```

Model errors become the list returned by `errors.full_messages()`:

```python
return self.render(json=post.errors, status=422)
# Example body: ["Field title is blank"]
```

An empty error collection becomes `[]`. Scaffold create/update actions use this
format for JSON validation failures. See
[model serialization](../models/index.md#temporary-attributes-and-serialization)
for field selection and authentication-secret filtering.

### Headers and response state

Use `self.response` to set headers or status before preparing the body. These
metadata changes carry into the final response unless explicitly replaced; they
do not mark the response as performed.

Rendering sets `self.performed`. This tracks whether a response has been prepared,
not whether the action has finished executing.

## Redirects and empty responses

```python
return self.redirect_to(product_path(product), notice="Saved")
return self.redirect_to(products_path(), status=303, alert="Product removed")
return self.head(204, headers={"X-Result": "complete"})
```

Redirects can include a `notice` or `alert`. `head` prepares an empty response.
Both use the same response tracking as `render` and `respond_to`.

As with rendering, return their result when the action should stop. In a before
callback, preparing a response stops the callback chain even without a return.

## Content negotiation

Use `respond_to` to serve HTML and JSON from the same action:

```python
from app.models.post import Post
from flaskteroids.controller import ActionController


class PostsController(ActionController):
    def index(self):
        self.posts = Post.all()
        self.respond_to(
            html=lambda: self.render("index"),
            json=lambda: self.render(json=self.posts),
        )
```

A `.json` URL suffix takes precedence over the `Accept` header. Without either,
HTML is selected. A requested format you do not offer returns **406 Not Acceptable**.

The selected response is recorded on the controller, so returning it is optional.
HTML handlers can leave template rendering implicit. JSON handlers must render
or return a response.

## Controller callbacks

Use callbacks for work shared by several actions, such as loading a record or
checking authentication:

```python
from app.models.post import Post
from flaskteroids.actions import before_action
from flaskteroids.controller import ActionController


class PostsController(ActionController):
    before_action("_set_post", only=["show", "edit", "update", "destroy"])

    def show(self):
        pass  # The callback has loaded self.post; render show.html.

    def _set_post(self):
        self.post = Post.find(self.params["id"])
```

Import declarations explicitly and call them inside the class. Controllers use
the same [declaration rules](../models/index.md#class-body-declarations) as models
and mailers, including inheritance through ordinary mixins.

### Inherited actions

Child controllers inherit actions and callbacks. A callback without `only` also
covers actions added by the child. Calling `super().action()` runs the parent
action and its callbacks. Mailers follow the same rules.

### Around and after callbacks

An `around_action` method is a generator: setup runs before `yield`, and cleanup
runs after it. Yield exactly once to run the action:

```python
from time import monotonic

from app.models.post import Post
from flask import current_app
from flaskteroids.actions import around_action
from flaskteroids.controller import ActionController


class PostsController(ActionController):
    around_action("_log_duration")

    def index(self):
        self.posts = Post.all()

    def _log_duration(self):
        started = monotonic()
        yield
        current_app.logger.info("Action duration: %.3fs", monotonic() - started)
```

On a successful request, the order is:

1. Before callbacks, in declaration order.
2. Around callback setup, in declaration order.
3. The action and any implicit template rendering.
4. Around cleanup, in reverse order.
5. After callbacks, in declaration order.

After callbacks can edit `self.response`, but cannot prepare a second response.

### Stopping callbacks and handling failures

- A before callback that prepares or returns a response skips the action and the
  remaining before, around, and after callbacks.
- An around generator that returns before `yield` skips the action, later around
  callbacks, and after callbacks. Its return value is the response; `None` leaves
  implicit rendering in place. Earlier around callbacks still clean up.
- A second yield raises `ProgrammerError` and closes the generator.
- Entered around generators resume and close even if the action or later setup
  fails. Cleanup resumes normally; the action exception is not thrown into the
  generator. After callbacks run only if the action and cleanup succeed.

A cleanup failure does not prevent other cleanup from running. If an action or
setup exception is already being raised, it remains the primary exception;
cleanup failures are logged and added to its notes. Otherwise, the first cleanup
failure is raised, with later failures logged and added as notes.

## Controller helpers

Presentation helper classes in `app/helpers/*_helper.py` are automatically
available to views. Their methods run on the view context, not the controller.
Use [`helper(...)`](../views/index.md#restricting-automatic-inclusion) to include
extra classes when automatic inclusion is restricted.

To expose a method that needs controller state, use `helper_method`:

```python
from app.controllers.application_controller import ApplicationController
from flaskteroids.controller import helper_method


class PostsController(ApplicationController):
    helper_method("_display_name")

    def _display_name(self, post):
        return post.title or "Untitled"
```

Call it in a template, layout, or partial:

```html
{{ display_name(post) }}
```

The template name drops the leading underscore by default. Set
`name="another_name"` to choose a different name. These helpers are inherited,
use the current controller, and remain private methods rather than routable
actions. Other private methods are not exposed. Return ordinary strings for
text that should be HTML-escaped.

Mailers provide the same declaration through `flaskteroids.mailer.helper_method`,
but delegate to the mailer's state. See
[mailer helpers](../other/mailers.md#mailer-helper-methods).

The authentication generator exposes `is_authenticated()` this way. It resumes
the session on demand, so public pages can show login/logout controls without an
extra callback. Calling it does not require login; `_require_authentication`
enforces access control.
