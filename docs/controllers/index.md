# Controllers

Controllers handle HTTP requests. Each action is a method on a controller class. If an action returns `None`, Flaskteroids renders its matching template and passes the controller's instance variables to it. Explicit responses, including empty strings and dictionaries, are returned unchanged.

```python
# app/controllers/posts_controller.py
from flaskteroids import params
from flaskteroids.controller import ActionController
from app.models.post import Post

class PostsController(ActionController):
    def index(self):
        self.posts = Post.all()
        # Implicitly renders app/views/posts/index.html and
        # makes self.posts available in the template.

    def show(self):
        self.post = Post.find(params["id"])
        # Implicitly renders app/views/posts/show.html and
        # makes self.post available in the template.
```

## Controller callbacks

Declare `before_action` inside `@rules` to run code before an action. Use it to load records shared by several actions or check authentication:

```python
from flaskteroids import params
from flaskteroids.actions import before_action
from flaskteroids.rules import rules
from flaskteroids.controller import ActionController
from app.models.post import Post

@rules(
    before_action('_set_post', only=['show', 'edit', 'update', 'destroy'])
)
class PostsController(ActionController):
    def show(self):
        # self.post is already set by the callback
        pass

    def _set_post(self):
        self.post = Post.find(params["id"])
```

### Inherited actions

Children inherit actions and callback rules. Callbacks without `only` also cover
actions the child adds. Calling `super().action()` runs the parent action and its
callbacks. The same rules apply to mailers.

### Around and after callbacks

`around_action` methods are generators. Code before `yield` runs before the
action; code after it runs during cleanup:

```python
from time import monotonic
from flask import current_app
from flaskteroids.actions import around_action

@rules(around_action('_log_duration'))
class PostsController(ActionController):
    def index(self):
        self.posts = Post.all()

    def _log_duration(self):
        started = monotonic()
        yield
        current_app.logger.info("Action duration: %.3fs", monotonic() - started)
```

The callback chain follows these rules:

- Before callbacks run in declaration order. A truthy return value is used as the
  response and skips the action, around callbacks, and after callbacks.
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
- After callbacks run in declaration order only after the action and all around
  cleanup finish successfully. If an after callback raises, later after callbacks
  do not run.

A cleanup failure does not prevent other entered generators from unwinding. If
an action or setup exception is already propagating, it remains the exception
raised to the caller. Secondary cleanup failures are logged and added to its
exception notes. Otherwise, the first cleanup exception is raised and any later
cleanup failures are logged and added as notes to it.

## Rendering responses

`render('new', status=422)` renders an HTML template with the requested status.
Without an action argument, `render(json=value, status=200)` returns JSON and
preserves the requested status, including `HTTPStatus` values.

Supported payloads include dictionaries, lists, strings, numbers, booleans, and
`None`. Empty dictionaries, lists, and strings remain JSON values; `None` becomes
JSON `null`. Tuples become JSON arrays.

Models, queries, and other objects with a callable `__json__()` use that protocol,
including when nested inside dictionaries, lists, or tuples. Values returned by
`__json__()` are processed recursively too. Other values are passed to Flask's
JSON provider, preserving its supported types and custom serialization.

```python
return render(json=[post, another_post])
return render(json={"posts": Post.all(), "featured": post})
```

Model errors serialize as the list returned by `errors.full_messages()`, including
`[]` when there are no errors:

```python
return render(json=post.errors, status=422)
# JSON body on validation failure: ["Field title is blank"]
```

Generated scaffold create and update actions use this response for JSON
validation failures. See [model serialization](../models/index.md#json-serialization)
for column selection and authentication-field filtering.

## Controller helpers

Use `helper_method` inside `@rules` to expose a private controller method as a
callable in templates, layouts, and partials:

```python
from flaskteroids import rules
from flaskteroids.controller import helper_method

@rules(helper_method("_display_name"))
class PostsController(ApplicationController):
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

The authentication generator uses this mechanism to expose `is_authenticated()`.
The helper resumes the session on demand, so public pages can show login/logout
controls without a separate authentication-status callback. Calling the helper
does not require login; `_require_authentication` enforces access control.

## Content negotiation

Use `respond` to return HTML or JSON from the same action. It selects a handler based on the request's `Accept` header or a `.json` URL suffix:

```python
from flaskteroids.controller import ActionController, render, respond
from app.models.post import Post

class PostsController(ActionController):
    def index(self):
        self.posts = Post.all()
        return respond(
            html=lambda: render('index'),
            json=lambda: render(json=self.posts)
        )
```
