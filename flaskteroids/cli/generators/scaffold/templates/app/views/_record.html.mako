<div id="${model_ref}-{{ ${model_ref}.id }}">
% for field in fields:
    <p>
      <strong>${field['name'].title()}</strong>
      {{ ${model_ref}.${field['name']} }}
    </p>
% endfor
% for attachment in attachments:
  {% if ${model_ref}.${attachment['name']}.attached() %}
    <p>
      <strong>${attachment['name'].title()}</strong>
      {% for blob in ${model_ref}.${attachment['name']}.blobs %}
        {{ link_to(blob.filename, blob_path(blob)) }}
      {% endfor %}
    </p>
  {% endif %}
% endfor
</div>
