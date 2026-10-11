# Forms

Use `form_with` to build model-backed forms and `params.expect` to filter submitted attributes.

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

Field helpers include `text_field`, `text_area`, `password_field`, and `checkbox`.

## Strong parameters

Use `params.expect` to select the attributes a controller may pass to a model. Do not pass unfiltered request data to `create` or `update`. Otherwise, users could change attributes you did not intend to expose, such as an admin flag.

`expect` checks the expected structure, including nested objects and lists. For a post form:

```python
# app/controllers/posts_controller.py
from flaskteroids import params, redirect_to
from flaskteroids.controller import ActionController, render
from flaskteroids.routes import post_path
from app.models.post import Post

class PostsController(ActionController):
    # ...

    def create(self):
        self.post = Post.new(**self._post_params())
        if self.post.save():
            return redirect_to(post_path(self.post))
        return render('new', status=422)

    def update(self):
        self.post = Post.find(params['id'])
        if self.post.update(**self._post_params()):
            return redirect_to(post_path(self.post))
        return render('edit', status=422)

    def _post_params(self):
        # Assumes form data is sent as:
        # post[title]=...
        # post[content]=...
        return params.expect(post=['title', 'content'])
```

`params.expect(post=['title', 'content'])` requires a top-level `post` dictionary and returns only its permitted attributes. It discards other attributes. If `post` is missing or has the wrong structure, it raises an exception.

## CSRF protection

Flaskteroids checks CSRF tokens on state-changing requests, meaning all methods except GET, HEAD, OPTIONS, and TRACE. `form_with` includes the token for you.

Tokens are signed, expire after one hour, and are bound to a random nonce stored in
the browser session. A token from another session is rejected. Clearing the session
invalidates its tokens; reload forms to obtain a new token. Token generation requires
an active request context and a configured Flask secret key. AJAX requests can send
the token in the `X-CSRF-TOKEN` header instead of the `csrf_token` form field.

Do not store pages containing CSRF tokens in a shared cache. Tokens are specific to each session.
Applications upgrading from the old session-independent tokens must reload existing
forms.

Include the token yourself in manual forms:

```html
<form action="/posts" method="post">
  <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
  <!-- ... form fields -->
</form>
```
