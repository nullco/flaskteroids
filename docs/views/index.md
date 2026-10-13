# Views

Views are Jinja2 templates in `app/views`. By default, a controller action renders the template matching its controller and action name. For example, `PostsController.index` renders `app/views/posts/index.html`.

Controller instance variables become template variables. If the action sets `self.posts`, the template can use `posts`:

```html
<!-- app/views/posts/index.html -->
{% extends "layouts/application.html" %}

{% block body %}
<h1>Posts</h1>

<ul>
  {% for post in posts %}
  <li>{{ post.title }}</li>
  {% endfor %}
</ul>
{% endblock %}
```

## Helper escaping and URLs

`link_to()` and `button_to()` escape ordinary text and HTML attribute values.
Use `markupsafe.Markup` only for HTML you trust, such as an application-defined
icon or label. Never mark user input safe. Attributes are escaped even when
supplied as `Markup`.

`link_to()` accepts relative URLs, including protocol-relative URLs, and the
`http`, `https`, `mailto`, and `tel` schemes. Form helpers accept relative and
HTTP(S) action URLs. Unsupported schemes, such as `javascript` and `data`, and
URLs containing control characters raise `ValueError`. HTML escaping alone does
not make an executable URL safe.

These checks do not restrict destination hosts. Applications must validate
user-supplied destinations when links or forms should stay on a particular site.
Keep HTML attribute names application-defined. Invalid names raise `ValueError`;
valid event-handler attributes still contain executable code and must never come
from untrusted input.
