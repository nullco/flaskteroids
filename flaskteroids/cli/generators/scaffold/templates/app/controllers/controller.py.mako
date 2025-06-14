from flask import redirect, url_for
from flaskteroids import params
from flaskteroids.rules import rules
from flaskteroids.actions import before_action
from app.controllers.application_controller import ApplicationController
from app.models.${model_ref} import ${model}


@rules(
    before_action('_set_${singular}', only=['show', 'edit', 'update', 'destroy'])
)
class ${controller}Controller(ApplicationController):

    def index(self):
        self.${models_ref} = ${model}.all()

    def show(self):
        pass

    def new(self):
        self.${model_ref} = ${model}.new()

    def edit(self):
        pass

    def create(self):
        self.${model_ref} = ${model}.create(**self._${model_ref}_params())
        if self.${model_ref}.is_persisted():
            return redirect(url_for('show_${singular}', id=self.${model_ref}.id))
        else:
            return redirect(url_for('new_${singular}'))

    def update(self):
        if self.${model_ref}.update(**self._${model_ref}_params()):
            return redirect(url_for('show_${singular}', id=self.${model_ref}.id))
        else:
            return redirect(url_for('new_${singular}'))

    def destroy(self):
        self.${model_ref}.destroy()
        return redirect(url_for('index_${singular}'))

    def _set_${model_ref}(self):
        self.${model_ref} = ${model}.find(id=params['id'])

    def _${model_ref}_params(self):
        return params.expect(${model_ref}=[${', '.join("'" + field['name'] + "'" for field in fields)}])
