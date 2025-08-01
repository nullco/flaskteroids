{% call(form) form_with(model=${model_ref}) %}
  {% if ${model_ref}.errors %}
    <div style="color: red">
      <h2>some errors prohibited this resource from being saved:</h2>
      <ul>
      {% for error in ${model_ref}.errors %}
        <li>{{ error.full_message }}</li>
      {% endfor %}
      </ul>
    </div>
  {% endif %}

% for field in fields:
    <div>
      {{ form.label('${field['name']}', style='display: block') }}
      % if field['type'] == 'text':
      {{ form.text_area('${field['name']}' }}
      % elif field['type'] == 'int':
      {{ form.number_field('${field['name']}' }}
      % elif field['type'] == 'bool':
      {{ form.checkbox('${field['name']}' }}
      % else:
      {{ form.text_field('${field['name']}' }}
      % endif
    </div>
% endfor

  <div>
    {{ form.submit() }}
  </div>
{% endcall %}
