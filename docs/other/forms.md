# Forms

A form has two parts: the template that builds inputs, and the controller that
accepts their values. Use `form_with` to build the form and `self.params.expect`
to choose which submitted attributes may reach your model.

## Building forms

Pass a model to `form_with`. It chooses the destination and HTTP method, supplies
field values, and includes a CSRF token. Inside the block, use `form` to create
labels and inputs:

```html
<!-- app/views/posts/_form.html -->
{% call(form) form_with(model=post) %}
  <div>
    {{ form.label("title") }}
    {{ form.text_field("title") }}
  </div>

  <div>
    {{ form.label("content") }}
    {{ form.text_area("content") }}
  </div>

  <div>
    {{ form.submit("Save") }}
  </div>
{% endcall %}
```

### Destinations and HTTP methods

For a conventional `Post` resource:

| Model state | Destination | Method |
| --- | --- | --- |
| New record | `/posts` | POST |
| Saved record | `/posts/<id>` | PATCH |

Browsers submit PATCH as POST with a hidden `_method` field. Set `method` to
override the default; `method="PUT"` also works for updates.

An explicit URL changes only the destination. The model still supplies values,
errors, and default method inference:

```html
{% call(form) form_with(model=post, url="/review", method="POST") %}
  {{ form.text_field("title") }}
  {{ form.submit("Review") }}
{% endcall %}
```

With a persisted `post`, omitting `method="POST"` here would infer PATCH, not POST.
`url=None` (or omission) permits inference; `url=False` omits `action`; `url=""`
keeps an explicit empty action targeting the current page.

Ordinary nested model destinations accept a list or tuple:

```html
{% call(form) form_with(model=[product, subscriber]) %}
  {{ form.email_field("email") }}
  {{ form.submit("Subscribe") }}
{% endcall %}
```

A new child submits to `product_subscribers_path(product)` with POST; a persisted
child submits to `product_subscriber_path(product, subscriber)` with PATCH.
Fields use the child prefix (`subscriber[email]`) and child values, including
rejected input. `scope="signup"` overrides that prefix without changing the
model that supplies values and errors. A missing parent identifier raises an
error. Nested URLs do **not** automatically save nested model attributes.

### Choose a field helper

Field helpers include `text_field`, `text_area`, `password_field`, and `checkbox`.
Use `file_field('avatar')` or `file_field('documents', multiple=True)` for uploads.
`form_with` detects these fields and adds multipart encoding. See
[Attachments](attachments.md) for attachment forms and permitted parameters.

Use `form.rich_text_area("content")` for declared rich-text attributes. Install
Trix and storage with `bin/flask rich_text:install`, then migrate. See
[Rich text](rich_text.md) for setup, rendering, and validation.

## Buttons that submit forms

```html
{{ button_to("Create", "/products") }}
{{ button_to("Save", product) }}
{{ button_to("Delete", product, method="DELETE") }}
{{ button_to("Log out", session_path(), method="DELETE") }}
```

The default is POST for an explicit URL or new record and PATCH for a persisted
record. Nested model sequences infer from the final record, just like forms.
Deletion is always explicit. GET and POST render native HTML methods;
PUT/PATCH/DELETE render POST plus the corresponding hidden override. GET forms
include neither CSRF tokens nor method overrides, preventing tokens in query
strings. Unsafe forms include a CSRF token.

Button attributes and form attributes are separate:

```html
{{ button_to("Save", product, id="save-button", form={"id": "save-form", "class": "inline"}) }}
```

Labels and attributes are escaped; trusted `Markup` is permitted for labels,
not unescaped attributes. Unsupported/executable destination schemes are rejected.
`button_to` does not support omitting the action, adding arbitrary extra hidden
parameters, or remote/Turbo options.

## Form values and escaping

Forms show the original submitted scalar input before type conversion, plus
assigned writable virtual fields. If there is no pending input, they use saved
values. A failed validation therefore redisplays what the user entered, even if
type conversion would otherwise lose information.

Authentication secrets, digests, confirmations, and reset tokens are excluded by
default. Forms do not use JSON response serialization or evaluate read-only virtual
fields such as reset tokens. Re-enter passwords after an unsuccessful submission.

Field names, prefixes, attribute values, input values, and textarea values are
escaped. Keep field names and attribute names application-defined. Invalid HTML
attribute names raise `ValueError`. Do not construct field attributes from
unfiltered request data.

`collection_select()` escapes ordinary option labels and prompts. Explicit
`markupsafe.Markup` is accepted for trusted labels and prompts, but option values
and other field values are always escaped, even when supplied as `Markup`.

Form actions accept relative URLs, including protocol-relative URLs, and
HTTP(S) URLs. Other schemes and URLs containing control characters raise
`ValueError`. This policy prevents executable schemes; it does not restrict
which hosts a form may submit to. Check destinations separately if they come
from user input.

## Strong parameters

Strong parameters are an allowlist of attributes a controller may pass to a
model. Use `self.params.expect` for this filtering. **Do not pass unfiltered request
data to `create` or `update`**: users could change fields you did not intend to
expose, such as an admin flag.

`expect` also checks the input's structure, including nested objects and lists.
For a post form:

```python
# app/controllers/posts_controller.py
from app.models.post import Post
from flaskteroids.controller import ActionController
from flaskteroids.routes import post_path


class PostsController(ActionController):
    # ...

    def create(self):
        self.post = Post.new(**self._post_params())
        if self.post.save():
            return self.redirect_to(post_path(self.post))
        return self.render("new", status=422)

    def update(self):
        self.post = Post.find(self.params["id"])
        if self.post.update(**self._post_params()):
            return self.redirect_to(post_path(self.post))
        return self.render("edit", status=422)

    def _post_params(self):
        # Assumes form data is sent as:
        # post[title]=...
        # post[content]=...
        return self.params.expect(post=["title", "content"])
```

`self.params.expect(post=["title", "content"])` requires a top-level `post`
dictionary, but its nested fields are permitted, not required. It returns only submitted,
permitted attributes and discards other attributes. The same allowlist works for
both creation and partial updates:

```python
# Submitted: post[content]=Updated
attributes = self.params.expect(post=["title", "content"])
# attributes == {"content": "Updated"}
post.update(**attributes)  # The existing title is unchanged.
```

This also applies recursively to nested dictionaries and arrays of dictionaries.
Omitted fields are not filled with defaults; an explicitly submitted `None` scalar
is retained. Use model validations to require attributes, rather than treating the
allowlist as validation.

### Missing or malformed input

- A missing, null, or empty root raises `MissingParameter`. This includes a
  dictionary with no permitted attributes left after filtering.
- A required scalar root such as `self.params.expect("password")` rejects blank
  strings, but accepts `False` and numeric zero.
- An incorrect type raises `InvalidParameter`. Optional fields must still have
  the expected structure when submitted.

During HTTP requests, Flaskteroids automatically translates `MissingParameter`
and `InvalidParameter` into **400 Bad Request** responses; controllers do not
need to catch them. The default response is an HTML error page, including when
JSON is requested. Applications can customize either response with Flask's
`register_error_handler()` in an initializer (for example, to return JSON).
Direct calls outside request dispatch still raise these exceptions. Programmer
errors and unrelated exceptions are not translated into 400 responses.

## CSRF protection

Cross-site request forgery (CSRF) is an attempt to make someone's browser submit
an unwanted request while they are logged in. A session-bound token helps the
server verify that a form came from your application.

Flaskteroids checks CSRF tokens on state-changing requests, meaning all methods
except GET, HEAD, OPTIONS, and TRACE. `form_with` and `button_to` include the token
for unsafe forms, never GET forms. An overridden DELETE receives the same
protection as an actual DELETE request.
See [Routing](../controllers/routing.md#html-method-overrides).

Tokens belong to the browser session and expire after one hour. Clearing the
session invalidates its tokens; reload forms to obtain a new token. AJAX requests
can send the token in the `X-CSRF-TOKEN` header instead of the `csrf_token` form
field. Do not store pages containing CSRF tokens in a shared cache.

Include the token yourself in manual forms:

```html
<form action="/posts" method="post">
  <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
  <!-- ... form fields -->
</form>
```
