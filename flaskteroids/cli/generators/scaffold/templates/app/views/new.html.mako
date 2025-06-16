{% extends "layouts/application.html" %}

{% block title %}New ${singular}{% endblock %}

{% block body %}
<h1>New ${singular}</h1>

{% with ${singular}=${singular} %}
{% include "${plural}/_form.html" %}
{% endwith %}

<br>

<div>
  <a href="{{ url_for('index_${singular}') }}">Back to ${plural}</a>
</div>
{% endblock %}
