from http import HTTPStatus
from flask import url_for
from flaskteroids import params, rules, redirect_to
from flaskteroids.actions import before_action
from flaskteroids.controller import render, head, respond
from app.controllers.application_controller import ApplicationController
from app.models.${model_ref} import ${model}


@rules(
    before_action('_set_${singular}', only=['show', 'edit', 'update', 'destroy'])
)
class ${controller}Controller(ApplicationController):

    def index(self):
        self.${models_ref} = ${model}.all()
        return respond(
            html=lambda: render('index'),
            json=lambda: render(json=self.${models_ref})
        )

    def show(self):
        return respond(
            html=lambda: render('show'),
            json=lambda: render(json=self.${model_ref})
        )

    def new(self):
        self.${model_ref} = ${model}.new()

    def edit(self):
        pass

    def create(self):
        self.${model_ref} = ${model}.create(**self._${model_ref}_params())
        if self.${model_ref}.save():
            return respond(
                html=lambda: redirect_to(url_for('show_${singular}', id=self.${singular}.id), notice="${singular.title()} was successfully created."),
                json=lambda: render(json=self.${model_ref})
            )
        else:
            return respond(
                html=lambda: render('new', status=HTTPStatus.UNPROCESSABLE_ENTITY),
                json=lambda: render(json=self.${model_ref}.errors, status=HTTPStatus.UNPROCESSABLE_ENTITY)
            )

    def update(self):
        if self.${model_ref}.update(**self._${model_ref}_params()):
            return respond(
                html=lambda: redirect_to(url_for('show_${singular}', id=self.${model_ref}.id), notice="${singular.title()} was successfully updated."),
                json=lambda: render(json=self.${model_ref})
            )
        else:
            return respond(
                html=lambda: render('edit', status=HTTPStatus.UNPROCESSABLE_ENTITY),
                json=lambda: render(json=self.${model_ref}.errors, status=HTTPStatus.UNPROCESSABLE_ENTITY)
            )

    def destroy(self):
        self.${model_ref}.destroy()
        return respond(
            html=lambda: redirect_to(url_for('index_${singular}'), status=HTTPStatus.SEE_OTHER),
            json=lambda: head(HTTPStatus.NO_CONTENT)
        )

    def _set_${model_ref}(self):
        self.${model_ref} = ${model}.find(id=params['id'])

    def _${model_ref}_params(self):
        return params.expect(${model_ref}=[${', '.join("'" + field['name'] + "'" for field in fields)}])
