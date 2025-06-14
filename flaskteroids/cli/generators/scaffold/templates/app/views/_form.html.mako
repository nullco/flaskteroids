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
      {{ form.label('${field['name']}') }}
      {{ form.text_field('${field['name']}', style='display: block') }}
    </div>
% endfor

  <div>
    {{ form.submit() }}
  </div>
{% endcall %}
