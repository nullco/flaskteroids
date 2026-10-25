<div id="{{ dom_id(${model_ref}) }}">
% for field in fields:
    <p>
      <strong>${field['name'].title()}</strong>
      {{ ${model_ref}.${field['name']} }}
    </p>
% endfor
% for rich_text in rich_texts:
    <div>
      <strong>${rich_text.title()}</strong>
      {{ ${model_ref}.${rich_text} }}
    </div>
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
