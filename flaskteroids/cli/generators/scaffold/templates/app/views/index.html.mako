{% extends layout %}

{% block title %}${plural}{% endblock %}

{% block body %}

<p style="color: green">{{ flash.notice }}</p>

<h1>${plural.title()}</h1>

<div id="${plural}">
  {%  for ${model_ref} in ${models_ref} %}
    {% with ${model_ref}=${model_ref} %}
    {% include "${plural}/_${model_ref}.html" %}
    {% endwith %}
    <a href="{{ ${singular}_path(${model_ref}) }}">Show this ${singular}</a>
  {%  endfor %}
</div>


<a href="{{ new_${singular}_path() }}">New ${singular}</a>

{% endblock %}
