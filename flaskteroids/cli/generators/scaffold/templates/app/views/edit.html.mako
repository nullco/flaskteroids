{% extends "layouts/application.html" %}

{% block title %}Edit ${singular}{% endblock %}

{% block body %}
<h1>Edit ${singular}</h1>

{% with ${singular}=${singular} %}
{% include "${plural}/_form.html" %}
{% endwith %}

<br>

<div>
  <a href="{{ url_for('show_${singular}', id=${model_ref}.id) }}">Show this ${singular}</a>
  <a href="{{ url_for('index_${singular}') }}">Back to ${plural}</a>
</div>
{% endblock %}
