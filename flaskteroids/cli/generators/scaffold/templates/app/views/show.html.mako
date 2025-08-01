{% extends "layouts/application.html" %}

{% block title %}Show ${singular}{% endblock %}

{% block body %}
<p style="color: green">{{ flash.notice }}</p>

{% with ${singular}=${singular} %}
{% include "${plural}/_${singular}.html" %}
{% endwith %}

<div>
  <a href="{{ url_for('edit_${singular}', id=${singular}.id) }}">Edit this ${singular}</a> |
  <a href="{{ url_for('index_${singular}') }}">Back to ${plural}</a>
  {{ button_to('Destroy this ${singular}', ${singular}, 'delete') }}
</div>
{% endblock %}
