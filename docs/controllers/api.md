# Building an API

Use an API-only application when your clients need data rather than server-rendered
pages—for example, a mobile app or a separate JavaScript frontend. You still use
Flaskteroids models, routes, controllers, jobs, and mailers, but return JSON instead
of rendering browser views.

This guide builds a small posts API. If you have not installed Flaskteroids yet,
follow the [installation steps](../getting_started.md#prerequisites) first.

## Create the application

```sh
flask new blog --api
cd blog
```

The generator installs dependencies and prepares the development database. Run
application commands with `bin/flask`; no environment activation is needed.

Generate a resource and apply its migration:

```sh
bin/flask generate scaffold Post title:string content:text
bin/flask db:migrate
bin/flask run
```

The scaffold creates a model, migration, routes, controller, and request tests.
It does not create HTML views or forms.

## Make a request

In another terminal, create a post:

```sh
curl -i http://127.0.0.1:5000/posts \
  -H 'Content-Type: application/json' \
  -d '{"post": {"title": "Hello", "content": "My first post."}}'
```

The response has status **201 Created**, the saved post as JSON, and a `Location`
header pointing to its URL. Fetch the collection with:

```sh
curl http://127.0.0.1:5000/posts
```

The generated resource supports these requests:

| Method | Path | Result on success |
| --- | --- | --- |
| GET | `/posts` | 200 with a JSON array of posts |
| GET | `/posts/<id>` | 200 with one post |
| POST | `/posts` | 201 with the created post and a Location header |
| PATCH/PUT | `/posts/<id>` | 200 with the updated post |
| DELETE | `/posts/<id>` | 204 with an empty body |

There are no `new` or `edit` pages: the client supplies the interface. Resource
routes omit those actions unless explicitly requested with `only`. Nested and
singular resources follow the same convention. Resource helpers accept
`format="json"`; API-only applications do not add Turbo Stream routes.

Visit `/posts`, not `/`: an application without a root route returns 404 rather
than a welcome page.

## Work with controllers

Open `app/controllers/application_controller.py`:

```python
from flaskteroids.controller import APIController


class ApplicationController(APIController):
    pass
```

Your controllers inherit from this base. They use the same callbacks, strong
parameters, model serialization, headers, localization, and redirects as browser
controllers. The difference is the default response: an action that neither
renders nor returns a response sends **204 No Content**, rather than looking for
a template.

The scaffold's `create` action builds a post from permitted input, saves it, and
renders either the record or its validation errors:

```python
    def create(self):
        self.post = Post.new(**self._post_params())
        if self.post.save():
            return self.render(json=self.post, status=201, location=self.post)
        return self.render(json=self.post.errors, status=422)

    def _post_params(self):
        return self.params.expect(post=["title", "content"])
```

`location=` accepts a URL string, a saved model, or a nested model sequence.
Models resolve to a relative resource URL. Models and queries use the framework's
[JSON serialization](index.md#json-values); validation errors become a list of
full messages. Rejected saves and destructions return **422** in scaffold actions.

Use `self.head(status)` for an empty response, or return an ordinary Flask
response for files and plain text. API-only does not mean JSON-only, and explicit
JSON rendering does not require an Accept header. As with browser controllers,
prepare only one response per action.

You can also use `APIController` in an application that serves browser pages.
It does not change the behavior of other controllers using `Controller`.

## Accept JSON input

JSON request bodies populate `self.params`. Both of these bodies work with
`self.params.expect(post=["title"])`:

```json
{"post": {"title": "Hello"}}
```

```json
{"title": "Hello"}
```

By convention, the controller wraps unwrapped input under its model name while
retaining the original values. An existing root is never replaced. When a
conventional model exists, wrapping selects mapped columns and writable framework
attributes. **Wrapping does not permit attributes for assignment:** always filter
input with [strong parameters](../other/forms.md#strong-parameters).

To customize wrapping, declare it inside the controller class:

```python
from flaskteroids.controller import APIController, wrap_parameters


class EventsController(APIController):
    wrap_parameters(False)
```

Use `wrap_parameters("event")` for a custom root, or `wrap_parameters(True)` to
restore conventional wrapping. Subclasses inherit the declaration and can
override it independently. Forms and multipart uploads keep their usual
parameter conventions.

Request parsing also accepts `application/*+json`. Body values are merged with
query parameters, then path parameters; later sources take precedence.
Non-object JSON is available under `self.params["_json"]`. Malformed JSON returns
400.

For JSON database columns, scaffold fields such as `settings:json` use the
explicit `JSONValue` parameter schema. This preserves nested objects, arrays,
scalars, and null while other fields remain allowlisted independently. See
[JSON-valued fields](../other/forms.md#json-valued-fields).

## Test the API

Run the generated request tests:

```sh
bin/flask test
```

No browser is required. Add behavior-focused tests using the same request helpers
as a browser application, passing request bodies with `json=`:

```python
from test.test_helper import IntegrationTest, post


class PostsAPITest(IntegrationTest):
    def test_create_returns_saved_post(self):
        response = post("/posts", json={"post": {"title": "Hello"}})

        assert response.status_code == 201
        assert response.get_json()["title"] == "Hello"
```

Framework HTTP errors return JSON with `error` and `status` fields, preserving
headers such as `Retry-After` and `WWW-Authenticate`. Production errors do not
expose internal exception details; configured exception propagation remains
available for debugging. Validation errors rendered by your actions keep their
own representation. See [Testing](../testing.md) for fixtures and request helpers.

## Application defaults and authentication

The generated app sets `config.api_only = True` in `config/application.py`.
This selects application facilities, routing defaults, and generator output at
initialization; controller inheritance determines response behavior.

Models, migrations, jobs, mailers, translations, and file storage remain
available, including mailer templates and helpers. Browser views, application
helpers, assets, Turbo, and system tests are omitted. Generated CI does not
install a browser, and Docker builds do not precompile assets.

API requests are stateless by default. Cookie sessions, flash, browser form
method override, and the session-bound rich-text editor upload endpoint are not
installed. Stateless API controllers do not require browser CSRF tokens.
Browser controllers retain CSRF protection, even inside an API-only app.

The authentication generator builds a browser login workflow and cannot be used
in an API-only application. Cookie-session opt-ins, JWT, OAuth, and OpenAPI are
not built in. Choose an authentication approach appropriate for your clients;
do not enable cookie authentication by merely disabling CSRF protection.
