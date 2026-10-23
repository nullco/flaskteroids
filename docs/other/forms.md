# Forms

Use `form_with` to build model-backed forms and `self.params.expect` to filter submitted attributes.

## Building forms

`form_with(model=post)` chooses the form's action and HTTP method from the model and includes a CSRF token. Inside the template block, it exposes a `Form` object for generating labels and inputs:

```html
<!-- app/views/posts/_form.html -->
{% call(form) form_with(model=post) %}
  <div>
    {{ form.label('title') }}
    {{ form.text_field('title') }}
  </div>

  <div>
    {{ form.label('content') }}
    {{ form.text_area('content') }}
  </div>

  <div>
    {{ form.submit('Save') }}
  </div>
{% endcall %}
```

### Destinations and HTTP methods

New records infer their collection URL and POST. Persisted records infer their
member URL and **PATCH**, rendered as POST with a hidden `_method`. An explicit
method always wins; `method="PUT"` remains supported for an update.

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
value/error-owning model. Missing ancestor identities fail diagnostically.
Nested URLs do **not** enable nested-attribute mass assignment or persistence.

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
Action omission, arbitrary extra hidden button parameters, and remote/Turbo
options are not part of this bounded button API.

## Form values and escaping

Model-backed forms use before-type-cast scalar input and assigned writable virtual
fields, falling back to published mapped values. Failed validation therefore keeps
the original submission available even when a cast would lose information.
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

Use `self.params.expect` to select the attributes a controller may pass to a model. Do not pass unfiltered request data to `create` or `update`. Otherwise, users could change attributes you did not intend to expose, such as an admin flag.

`expect` checks the expected structure, including nested objects and lists. For a post form:

```python
# app/controllers/posts_controller.py
from flaskteroids.controller import ActionController
from flaskteroids.routes import post_path
from app.models.post import Post

class PostsController(ActionController):
    # ...

    def create(self):
        self.post = Post.new(**self._post_params())
        if self.post.save():
            return self.redirect_to(post_path(self.post))
        return self.render('new', status=422)

    def update(self):
        self.post = Post.find(self.params['id'])
        if self.post.update(**self._post_params()):
            return self.redirect_to(post_path(self.post))
        return self.render('edit', status=422)

    def _post_params(self):
        # Assumes form data is sent as:
        # post[title]=...
        # post[content]=...
        return self.params.expect(post=['title', 'content'])
```

`self.params.expect(post=['title', 'content'])` requires a top-level `post` dictionary,
but its nested fields are permitted, not required. It returns only submitted,
permitted attributes and discards other attributes. The same allowlist works for
both creation and partial updates:

```python
# Submitted: post[content]=Updated
attributes = self.params.expect(post=['title', 'content'])
# attributes == {'content': 'Updated'}
post.update(**attributes)  # The existing title is unchanged.
```

This also applies recursively to nested dictionaries and arrays of dictionaries.
Omitted fields are not filled with defaults; an explicitly submitted `None` scalar
is retained. Use model validations to require attributes, rather than treating the
allowlist as validation.

Missing, null, or empty roots raise `MissingParameter`, including dictionaries
with no permitted attributes after filtering. Required scalar roots, such as
`self.params.expect('password')`, reject blank strings but accept `False` and numeric
zero. Incorrect supplied types raise `InvalidParameter`; making fields optional
does not relax the expected structure.

During HTTP requests, Flaskteroids automatically translates `MissingParameter`
and `InvalidParameter` into **400 Bad Request** responses; controllers do not
need to catch them. The default response is an HTML error page, including when
JSON is requested. Applications can customize either response with Flask's
`register_error_handler()` in an initializer (for example, to return JSON).
Direct calls outside request dispatch still raise these exceptions. Programmer
errors and unrelated exceptions are not translated into 400 responses.

## CSRF protection

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
