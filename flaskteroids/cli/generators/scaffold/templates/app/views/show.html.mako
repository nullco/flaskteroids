{% extends "layouts/application.html" %}

{% block title %}Show ${singular}{% endblock %}

{% block head %}
<script>
    function destroy(url) {
        if (confirm("Are you sure?")) {
            fetch(url, {
                method: "DELETE",
                headers: {
                    'X-CSRF-TOKEN': "{{csrf_token()}}"
                }
            }).then(response => {
                if (response.ok) {
                } else if (response.redirected) {
                    window.location.href = response.url;
                } else {
                    alert("Failed to delete.");
                }
            });
        }
    }
</script>
{% endblock %}

{% block body %}
{% if params.notice %}<p style="color: green">{{ params.notice }}</p>{% endif %}

{% with ${singular}=${singular} %}
{% include "${plural}/_${singular}.html" %}
{% endwith %}

<div>
  <a href="{{ url_for('edit_${singular}', id=${singular}.id) }}">Edit this ${singular}</a>
  <a href="{{ url_for('index_${singular}') }}">Back to ${plural}</a>
  <button onclick="destroy('{{ url_for('destroy_${singular}', id=${model_ref}.id) }}')">Destroy this ${singular}</button>
</div>
{% endblock %}
