<!DOCTYPE html>
<html>
  <head>
    <meta charset="utf-8">
    <title>{% block title %}Test App{% endblock title %}</title>
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <script type="module" src="https://cdn.jsdelivr.net/npm/@hotwired/turbo@latest/dist/turbo.es2017-esm.min.js"></script>
    {% block head %}{% endblock head%}
  </head>

  <body>
    {% block body %}
    {% endblock body %}
  </body>
</html>
