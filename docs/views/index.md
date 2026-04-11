# Views

Views are the user-facing part of your application. Flaskteroids uses Jinja2 for templating, which is the default for Flask. Templates are located in the `app/views` directory and are automatically rendered by controller actions.

Instance variables set in the controller are available in the corresponding view file.

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
