# Controllers

Controllers handle HTTP requests. Each action is a method on a controller class.
Unless an action prepares a response, Flaskteroids renders its matching template
with the controller's instance variables. Native Flask response return values,
including empty strings and dictionaries, remain supported.

```python
# app/controllers/posts_controller.py
from flaskteroids.controller import ActionController
from app.models.post import Post

class PostsController(ActionController):
    def index(self):
        self.posts = Post.all()
        # Implicitly renders app/views/posts/index.html and
        # makes self.posts available in the template.

    def show(self):
        self.post = Post.find(self.params["id"])
        # Implicitly renders app/views/posts/show.html and
        # makes self.post available in the template.
```

Read request input from `self.params`; templates access the same mapping as
`params`. Use `self.params.expect(...)` to allowlist model attributes.

## Controller callbacks

Import declaration functions explicitly. They follow the same
[class-body declaration contracts](../models/index.md#class-body-declarations)
as models and mailers, including inheritance through ordinary mixins.

Call `before_action` inside the controller class to run code before an action. Use it to load records shared by several actions or check authentication:

```python
from flaskteroids.actions import before_action
from flaskteroids.controller import ActionController
from app.models.post import Post


class PostsController(ActionController):
    before_action("_set_post", only=["show", "edit", "update", "destroy"])

    def show(self):
        # self.post is already set by the callback
        pass

    def _set_post(self):
        self.post = Post.find(self.params["id"])
```

### Inherited actions

Children inherit actions and callback declarations. Callbacks without `only` also cover
actions the child adds. Calling `super().action()` runs the parent action and its
callbacks. The same rules apply to mailers.

### Around and after callbacks

`around_action` methods are generators. Code before `yield` runs before the
action; code after it runs during cleanup:

```python
from time import monotonic
from flask import current_app
from flaskteroids.actions import around_action


class PostsController(ActionController):
    around_action("_log_duration")

    def index(self):
        self.posts = Post.all()

    def _log_duration(self):
        started = monotonic()
        yield
        current_app.logger.info("Action duration: %.3fs", monotonic() - started)
```

The callback chain follows these rules:

- Before callbacks run in declaration order. Rendering a response stops the chain,
  even without a return value. Returning a response also skips the action, around
  callbacks, and after callbacks.
- Around callbacks enter in declaration order and unwind in reverse order.
  Entered generators are resumed and closed even if the action or a later
  callback's setup raises. Cleanup resumes the generator normally, rather than
  throwing the action exception into it.
- An around generator that returns before reaching `yield` skips the action,
  later around callbacks, and after callbacks. Its return value is used as the
  response. Returning `None` leaves implicit template rendering in place.
  Previously entered generators still unwind.
- Around generators must yield exactly once when they run the action. A second
  yield raises `ProgrammerError` and closes the generator.
- Implicit rendering happens before around cleanup and after callbacks. After
  callbacks run in declaration order only after the action and cleanup succeed;
  they can edit `self.response`, but cannot render a second response.

A cleanup failure does not prevent other entered generators from unwinding. If
an action or setup exception is already propagating, it remains the exception
raised to the caller. Secondary cleanup failures are logged and added to its
exception notes. Otherwise, the first cleanup exception is raised and any later
cleanup failures are logged and added as notes to it.

## Rendering responses

`self.render("new", status=422)` renders a template; `self.render()` selects the
current action. Use `self.render(json=value, status=200)` for JSON. Status values
can be integers or `HTTPStatus` members.

Rendering sets `self.response` but does not stop execution. Use
`return self.render(...)` when the action should exit immediately. A second render
raises `DoubleRenderError` from `flaskteroids.exceptions`.

Template/helper `render(...)` remains a partial renderer, not a controller response.

Supported payloads include dictionaries, lists, strings, numbers, booleans, and
`None`. Empty dictionaries, lists, and strings remain JSON values; `None` becomes
JSON `null`. Tuples become JSON arrays.

Models, queries, and other objects with a callable `__json__()` use that protocol,
including when nested inside dictionaries, lists, or tuples. Values returned by
`__json__()` are processed recursively too. Other values are passed to Flask's
JSON provider, preserving its supported types and custom serialization.

```python
self.render(json={"posts": Post.all(), "featured": post})
```

Model errors serialize as the list returned by `errors.full_messages()`, including
`[]` when there are no errors:

```python
return self.render(json=post.errors, status=422)
# JSON body on validation failure: ["Field title is blank"]
```

Generated scaffold create and update actions use this response for JSON
validation failures. See [model serialization](../models/index.md#temporary-attributes-and-serialization)
for column selection and authentication-field filtering.

## Controller helpers

Presentation methods in `app/helpers/*_helper.py` are automatically available to
views. Use [`helper(...)`](../views/index.md#restricting-automatic-inclusion) to
include additional helper classes when automatic inclusion is restricted.
These methods execute on the view context, not the controller.

Call `helper_method` inside the controller class to expose a private method as a
callable in templates, layouts, and partials:

```python
from flaskteroids.controller import helper_method


class PostsController(ApplicationController):
    helper_method("_display_name")

    def _display_name(self, post):
        return post.title or "Untitled"
```

```html
{{ display_name(post) }}
```

By default, the template name drops the method's leading underscore. Pass
`name="another_name"` to choose a different name. Helpers are inherited, use the
current controller instance, and remain private methods rather than routable
actions. Unregistered private methods are not exposed. Return ordinary strings
for text that should be HTML-escaped.

Mailers support the same declaration via `flaskteroids.mailer.helper_method`;
those helpers delegate to the mailer's own state, not a request controller.
See [mailer helper methods](../other/mailers.md#mailer-helper-methods).

The authentication generator uses this mechanism to expose `is_authenticated()`.
The helper resumes the session on demand, so public pages can show login/logout
controls without a separate authentication-status callback. Calling the helper
does not require login; `_require_authentication` enforces access control.

## Content negotiation

`self.respond_to(...)` selects an offered HTML or JSON handler using the `Accept`
header (HTML when absent); a `.json` URL suffix takes precedence. Unsupported
formats produce 406.
Selected responses are recorded on the controller, so returning the result is optional.
HTML handlers may leave template rendering implicit; JSON handlers must render or
return a response.

```python
from flaskteroids.controller import ActionController
from app.models.post import Post

class PostsController(ActionController):
    def index(self):
        self.posts = Post.all()
        self.respond_to(
            html=lambda: self.render('index'),
            json=lambda: self.render(json=self.posts)
        )
```
