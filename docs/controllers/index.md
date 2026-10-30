# Controllers

Controllers handle HTTP requests. Each action is a public method on a controller
class. Actions load or change model data, then render a page, return JSON, or
redirect the browser.

This guide uses browser controllers (`Controller`). For an application
that serves data without browser views, see [Building an API](api.md).

After reading this guide, you will know how to:

- Write an action and pass data to its view.
- Render responses, redirect, and accept permitted input.
- Share request behavior with controller callbacks.

## Write an action

If an action does not prepare a response, Flaskteroids renders its matching
template. Instance variables become template variables:

```python
# app/controllers/posts_controller.py
from app.models.post import Post
from flaskteroids.controller import Controller


class PostsController(Controller):
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

The template/helper function `render(...)` is different: it renders a record,
partial, or exact template to HTML, not a controller response. See
[view rendering](../views/turbo.md#builder-and-partials).

### JSON values

Pass a model, query, or ordinary JSON value to `render(json=...)`. Models use
their `__json__()` method to choose the attributes in the response. You can also
combine records and queries inside a dictionary:

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

### Turbo Frames and Stream responses

Controllers expose `self.turbo_frame_request` (boolean) and
`self.turbo_frame_request_id` (ID or `None`). Page views using `{% extends layout %}`
select `layout = "layouts/application.html"` normally and
`frame_layout = "layouts/turbo/frame.html"` for frame requests. Override either
path on the controller class or instance before rendering.

Use `self.render(turbo_stream=self.turbo_stream.remove(self.post))` for an HTTP
Stream response, or pass a list/tuple of operations. Templates can use the
conventional `<action>.turbo_stream.html` name. See
[Turbo Frames and Streams](../views/turbo.md) for examples, HTML fallback, and
[representation-specific cache validators](../views/turbo.md#caching-and-security).

### Headers and response state

Set response headers before rendering:

```python
self.response.headers["X-Report-Version"] = "1"
return self.render(json={"ready": True})
```

Setting a header does not prepare a response body. You can still render, redirect,
or return an empty response afterward.

## Redirects and empty responses

```python
return self.redirect_to(product_path(product), notice="Saved")
return self.redirect_to(products_path(), status=303, alert="Product removed")
return self.head(204, headers={"X-Result": "complete"})
```

Use status **303 See Other** after successful Turbo form mutations, and render
invalid HTML forms with **422** so Turbo can redisplay validation errors.

Redirects can include a `notice` or `alert`. `head` prepares an empty response.
Both use the same response tracking as `render` and `respond_to`.

As with rendering, return their result when the action should stop. In a before
callback, preparing a response stops the callback chain even without a return.

## Content negotiation

Use `respond_to` to serve HTML, JSON, or Turbo Streams from the same action:

```python
from app.models.post import Post
from flaskteroids.controller import Controller


class PostsController(Controller):
    def index(self):
        self.posts = Post.all()
        self.respond_to(
            html=lambda: self.render("index"),
            json=lambda: self.render(json=self.posts),
        )
```

A resource URL's `.json` or `.turbo_stream` suffix takes precedence over the
`Accept` header. Without either, HTML is selected. A requested format you do not
offer returns **406 Not Acceptable**.

Add a `turbo_stream=lambda: self.render()` handler to use a conventional Stream
template. Ordinary Turbo forms can fall back to offered HTML. See
[Stream negotiation](../views/turbo.md#negotiation-and-routes) for template fallback
and forced-format URLs.

The selected response is recorded on the controller, so returning it is optional.
HTML handlers can leave template rendering implicit. JSON handlers must render
or return a response.

## Controller callbacks

Use callbacks for work shared by several actions, such as loading a record or
checking authentication:

```python
from app.models.post import Post
from flaskteroids.actions import before_action
from flaskteroids.controller import Controller


class PostsController(Controller):
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
from flaskteroids.controller import Controller


class PostsController(Controller):
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

A before callback that prepares or returns a response stops the chain. Use this
for checks such as requiring login: redirecting to the login page prevents the
protected action from running.

An around callback must yield exactly once to run the action. Returning before
the yield skips it. Entered around callbacks still clean up if the action fails;
after callbacks run only when the action and cleanup succeed.

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
