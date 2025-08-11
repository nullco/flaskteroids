{% call(form) form_with(model=${model_ref}) %}
  {% if ${model_ref}.errors %}
    <div style="color: red">
      <h2>{{ ${model_ref}.errors | count }} errors prohibited this ${singular} from being saved:</h2>
      <ul>
      {% for message in ${model_ref}.errors.full_messages() %}
        <li>{{ message }}</li>
      {% endfor %}
      </ul>
    </div>
  {% endif %}

% for field in fields:
    <div>
      {{ form.label('${field['name']}', style='display: block') }}
      % if field['type'] == 'text':
      {{ form.text_area('${field['name']}') }}
      % elif field['type'] in ['int', 'integer']:
      {{ form.number_field('${field['name']}') }}
      % elif field['type'] in ['bool', 'boolean']:
      {{ form.checkbox('${field['name']}') }}
      % elif field['type'] == 'datetime':
      {{ form.datetime_field('${field['name']}') }}
      % elif field['type'] == 'date':
      {{ form.date_field('${field['name']}') }}
      % elif field['type'] == 'time':
      {{ form.time_field('${field['name']}') }}
      % else:
      {{ form.text_field('${field['name']}') }}
      % endif
    </div>
% endfor
% for ref in references:
    <div>
      {{ form.label('${ref['name']}', style='display: block') }}
      {{ form.text_field('${ref['name']}') }}
    </div>
% endfor

  <div>
    {{ form.submit() }}
  </div>
{% endcall %}
