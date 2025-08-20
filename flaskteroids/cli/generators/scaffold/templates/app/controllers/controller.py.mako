from http import HTTPStatus
from flask import url_for
from flaskteroids import params, rules, redirect_to
from flaskteroids.actions import before_action
from flaskteroids.controller import render, head, respond_to
from app.controllers.application_controller import ApplicationController
from app.models.${model_ref} import ${model}


@rules(
    before_action('_set_${singular}', only=['show', 'edit', 'update', 'destroy'])
)
class ${controller}Controller(ApplicationController):

    def index(self):
        self.${models_ref} = ${model}.all()
        with respond_to() as format:
            format.html(lambda: render('index'))
            format.json(lambda: render(json=self.${models_ref}))

    def show(self):
        with respond_to() as format:
            format.html(lambda: render('show'))
            format.json(lambda: render(json=self.${model_ref}))

    def new(self):
        self.${model_ref} = ${model}.new()

    def edit(self):
        pass

    def create(self):
        self.${model_ref} = ${model}.create(**self._${model_ref}_params())
        with respond_to() as format:
            if self.${model_ref}.save():
                format.html(lambda: redirect_to(url_for('show_${singular}', id=self.${singular}.id), notice="${singular.title()} was successfully created."))
                format.json(lambda: render(json=self.${model_ref}))
            else:
                format.html(lambda: render('new', status=HTTPStatus.UNPROCESSABLE_ENTITY))
                format.json(lambda: render(json=self.${model_ref}.errors, status=HTTPStatus.UNPROCESSABLE_ENTITY))

    def update(self):
        with respond_to() as format:
            if self.${model_ref}.update(**self._${model_ref}_params()):
                format.html(lambda: redirect_to(url_for('show_${singular}', id=self.${model_ref}.id), notice="${singular.title()} was successfully updated."))
                format.json(lambda: render(json=self.${model_ref}))
            else:
                format.html(lambda: render('edit', status=HTTPStatus.UNPROCESSABLE_ENTITY))
                format.json(lambda: render(json=self.${model_ref}.errors, status=HTTPStatus.UNPROCESSABLE_ENTITY))

    def destroy(self):
        self.${model_ref}.destroy()
        with respond_to() as format:
            format.html(lambda: redirect_to(url_for('index_${singular}'), status=HTTPStatus.SEE_OTHER))
            format.json(lambda: head(HTTPStatus.NO_CONTENT))

    def _set_${model_ref}(self):
        self.${model_ref} = ${model}.find(id=params['id'])

    def _${model_ref}_params(self):
        return params.expect(${model_ref}=[${', '.join("'" + field['name'] + "'" for field in fields)}])
