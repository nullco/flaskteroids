# Handling Forms

Handling user input from forms is a common task in web applications. Flaskteroids provides a cohesive set of tools to build forms, handle submissions securely, and prevent common vulnerabilities.

## Building Forms

Flaskteroids provides a simple and powerful way to build forms using the `form_with` helper and the `Form` object. The `form_with` helper can be used with a model object to automatically generate the form's action and method, and it also includes the CSRF token automatically.

Here's an example of how to create a form for a `Post` model:

```html
<!-- app/views/posts/_form.html -->
{%raw %}
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
{% endraw %}
```

The `form` object provides a variety of helpers for generating form fields, such as `text_field`, `text_area`, `password_field`, `checkbox`, and more.

## Strong Parameters

To prevent mass assignment vulnerabilities, Flaskteroids uses a technique inspired by Rails' **Strong Parameters**. The `params` object allows you to whitelist which parameters are permitted in your controller actions.

This is a security best practice that ensures users cannot update model attributes they are not supposed to, such as an admin flag.

Here's how you can use `params.expect` to safely handle incoming data. The `expect` method allows you to define the structure of the expected parameters, including nested objects and lists.

```python
# app/controllers/posts_controller.py
from flaskteroids import params
from flaskteroids.controller import ActionController
from app.models.post import Post

class PostsController(ActionController):
    # ...

    def create(self):
        self.post = Post.new(_post_params())
        if self.post.save():
            # ... success
        else:
            # ... error
            pass

    def update(self):
        self.post = Post.find(params['id'])
        if self.post.update(_post_params()):
            # ... success
        else:
            # ... error
            pass

    def _post_params(self):
        # Assumes form data is sent as:
        # post[title]=...
        # post[content]=...
        return params.expect(post=['title', 'content'])

```

In this example, `_post_params` specifies that the `params` object must contain a top-level key called `post`, which should be a dictionary containing only the `title` and `content` keys. Any other attributes within the `post` object will be discarded, and if the `post` key is missing or the structure is incorrect, an exception will be raised.

## CSRF Protection

Flaskteroids automatically includes CSRF (Cross-Site Request Forgery) protection on all non-GET requests. A CSRF token is generated and must be included in your forms. The `form_with` helper does this automatically.

For manual forms, you can include the token like this:

```html
<form action="/posts" method="post">
  <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
  <!-- ... form fields -->
</form>
```
