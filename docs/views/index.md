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
