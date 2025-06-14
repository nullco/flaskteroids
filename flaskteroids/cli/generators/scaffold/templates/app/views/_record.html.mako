<div id="${model_ref}-{{ ${model_ref}.id }}">
% for field in fields:
    <p>
      <strong>${field['name'].title()}</strong>
      {{ ${model_ref}.${field['name']} }}
    </p>
% endfor
</div>
