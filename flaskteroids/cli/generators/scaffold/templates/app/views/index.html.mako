{% extends "layouts/application.html" %}

{% block title %}${plural}{% endblock %}

{% block body %}

{% if params.notice %}<p style="color: green">{{ params.notice }}</p>{% endif %}

<h1>${plural.title()}</h1>

<div id="${plural}">
  {%  for ${model_ref} in ${models_ref} %}
    {% with ${model_ref}=${model_ref} %}
    {% include "${plural}/_${model_ref}.html" %}
    {% endwith %}
    <a href="{{ url_for('show_${singular}', id=${model_ref}.id) }}">Show this ${singular}</a>
  {%  endfor %}
</div>


<a href="{{ url_for('new_${singular}') }}">New ${singular}</a>

{% endblock %}
