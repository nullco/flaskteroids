from app.controllers.application_controller import ApplicationController
from app.models.${model_ref} import ${model}
% if any(field["type"] == "json" for field in fields):
from flaskteroids.actions import JSONValue, before_action
% else:
from flaskteroids.actions import before_action
% endif


class ${controller}Controller(ApplicationController):
    before_action("_set_${model_ref}", only=["show", "update", "destroy"])

    def index(self):
        self.${models_ref} = ${model}.${"with_all_rich_text()" if rich_texts else "all()"}
        return self.render(json=self.${models_ref})

    def show(self):
        return self.render(json=self.${model_ref})

    def create(self):
        self.${model_ref} = ${model}.new(**self._${model_ref}_params())
        if self.${model_ref}.save():
            return self.render(
                json=self.${model_ref}, status=201, location=self.${model_ref}
            )
        return self.render(json=self.${model_ref}.errors, status=422)

    def update(self):
        if self.${model_ref}.update(**self._${model_ref}_params()):
            return self.render(json=self.${model_ref})
        return self.render(json=self.${model_ref}.errors, status=422)

    def destroy(self):
        if self.${model_ref}.destroy():
            return self.head(204)
        return self.render(json=self.${model_ref}.errors, status=422)

    def _set_${model_ref}(self):
        self.${model_ref} = ${model}.find(self.params["id"])

    def _${model_ref}_params(self):
        permitted = [${', '.join(repr(field["name"]) for field in fields + references if field["type"] != "json")}]
% for field in fields:
% if field["type"] == "json":
        permitted.append(("${field['name']}", JSONValue))
% endif
% endfor
% for rich_text in rich_texts:
        permitted.append("${rich_text}")
% endfor
% for attachment in attachments:
        permitted.append(${"('" + attachment['name'] + "', [])" if attachment['type'] == 'attachments' else "'" + attachment['name'] + "'"})
% endfor
        return self.params.expect(${model_ref}=permitted) if permitted else {}
