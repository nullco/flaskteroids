{% extends layout %}

{% block title %}Edit ${singular}{% endblock %}

{% block body %}
<h1>Edit ${singular}</h1>

{% with ${singular}=${singular} %}
{% include "${plural}/_form.html" %}
{% endwith %}

<br>

<div>
  <a href="{{ ${singular}_path(${model_ref}) }}">Show this ${singular}</a>
  <a href="{{ ${collection}_path() }}">Back to ${plural}</a>
</div>
{% endblock %}
