{% extends "layouts/application.html" %}

{% block title %}Show ${singular}{% endblock %}

{% block body %}
<p style="color: green">{{ flash.notice }}</p>

{% with ${singular}=${singular} %}
{% include "${plural}/_${singular}.html" %}
{% endwith %}

<div>
  <a href="{{ edit_${singular}_path(${singular}) }}">Edit this ${singular}</a> |
  <a href="{{ ${plural}_path() }}">Back to ${plural}</a>
  {{ button_to('Destroy this ${singular}', ${singular}, method='delete') }}
</div>
{% endblock %}
