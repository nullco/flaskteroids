# API-only applications

Create an application with API-oriented defaults:

```sh
flaskteroids new inventory --api
cd inventory
bin/flask generate scaffold Post title:string content:text
bin/flask db:prepare
bin/flask run
```

The application retains models, migrations, jobs, mailers, translations, and file
storage. It omits browser views, helpers, assets, Turbo, system tests, and browser
installation steps in CI. Docker does not run asset precompilation. Mailer
templates and helpers remain available.

Scaffolds generate JSON CRUD and request tests. Resource routes default to
`index`, `show`, `create`, `update`, and `destroy`; there are no `new` or `edit`
routes unless explicitly requested with `only`. Nested and singular resources
follow the same conventions. Resource helpers support `format="json"`, but do
not add Turbo Stream routes. An application without a root route returns 404
rather than a browser welcome page.

## Application and controller defaults

The generated application sets `config.api_only = True` in
`config/application.py`. This selects boot facilities, routing defaults, and
generators during initialization. It does not change controller classes
dynamically.

The generated controller base is:

```python
from flaskteroids.controller import APIController


class ApplicationController(APIController):
    pass
```

API controllers share callbacks, strong parameters, JSON serialization, response
headers, localization, redirects, and the single-response lifecycle with browser
controllers. An action that neither renders nor returns a response produces
**204 No Content**, without looking for a template.

Use `self.render(json=value)`, `self.head(status)`, or return an ordinary Flask
response. API-only is not JSON-only: file and plain-text responses work too.
Explicit JSON rendering does not require an Accept header.

```python
def create(self):
    self.post = Post.new(**self.params.expect(post=["title", "content"]))
    if self.post.save():
        return self.render(json=self.post, status=201, location=self.post)
    return self.render(json=self.post.errors, status=422)
```

`location=` accepts a URL string, a saved model, or a nested model sequence.
Models resolve through resource routing to a relative Location URL. Models,
queries, and errors use their existing JSON serialization; validation errors
remain full-message lists. API scaffolds return 201 on creation, 200 on update,
204 on successful deletion, and 422 when a save or destruction is rejected.

You can also inherit from `APIController` in a normal browser application.
Existing `ActionController` classes keep their browser behavior.

## JSON input

JSON request bodies, including `application/*+json`, populate `self.params`.
Body values are merged with query parameters, then path parameters; later
sources take precedence. Non-object JSON is available under `self.params["_json"]`.
Malformed JSON returns 400.

By convention, a controller adds a model root for unwrapped JSON input while
retaining the original values. Both requests work with
`self.params.expect(post=["title"])`:

```json
{"post": {"title": "Hello"}}
```

```json
{"title": "Hello"}
```

Scaffolds permit `name:json` columns using the explicit `JSONValue` strong-parameter
schema, preserving nested objects, arrays, scalar values, and null. Other fields
remain allowlisted independently. See [JSON-valued fields](../other/forms.md#json-valued-fields).

An existing root is never replaced. When a conventional model exists, wrapping
selects mapped columns and writable framework attributes. Wrapping is not an
assignment allowlist: always use strong parameters.

Declare wrapping behavior inside the controller class:

```python
from flaskteroids.controller import APIController, wrap_parameters


class EventsController(APIController):
    wrap_parameters(False)
```

Use `wrap_parameters("event")` for a custom root, or `wrap_parameters(True)` to
restore conventional wrapping. Declarations are inherited; a subclass can override
its wrapping without changing parents or siblings. Forms and multipart uploads
retain their existing parameter conventions.

## Failures and testing

Framework HTTP failures use JSON with `error` and `status` fields. HTTP headers
such as Retry-After and WWW-Authenticate are preserved. Production errors do not
expose internal exception details; configured exception propagation remains
available for debugging. Application-rendered validation errors retain their own
representation.

Use the existing request helpers with JSON:

```python
response = post("/posts", json={"post": {"title": "Hello"}})
assert response.status_code == 201
assert response.get_json()["title"] == "Hello"
```

Run `bin/flask test`; no browser is required.

## Current boundaries

API requests are stateless by default: cookie sessions, flash, browser form
method override, and the session-bound rich-text editor upload endpoint are not
installed. Stateless API controllers do not require browser CSRF tokens.
Browser controllers retain CSRF protection, including inside an API-only app.

Authentication generation and cookie-session opt-ins are deferred. The
authentication generator rejects API-only applications before writing files.
Do not implement cookie-authenticated API actions by merely disabling CSRF.
JWT, OAuth, OpenAPI, and a new serializer/error-envelope standard are not
provided by this feature.
