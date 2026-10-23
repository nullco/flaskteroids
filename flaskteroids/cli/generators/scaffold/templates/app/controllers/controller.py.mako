from http import HTTPStatus
from flaskteroids.actions import before_action
from flaskteroids.routes import ${collection}_path, ${singular}_path
from app.controllers.application_controller import ApplicationController
from app.models.${model_ref} import ${model}


class ${controller}Controller(ApplicationController):
    before_action('_set_${singular}', only=['show', 'edit', 'update', 'destroy'])

    def index(self):
        self.${models_ref} = ${model}.${"with_all_rich_text()" if rich_texts else "all()"}
        return self.respond_to(
            html=lambda: self.render('index'),
            json=lambda: self.render(json=self.${models_ref})
        )

    def show(self):
        return self.respond_to(
            html=lambda: self.render('show'),
            json=lambda: self.render(json=self.${model_ref})
        )

    def new(self):
        self.${model_ref} = ${model}.new()

    def edit(self):
        pass

    def create(self):
        self.${model_ref} = ${model}.new(**self._${model_ref}_params())
        if self.${model_ref}.save():
            return self.respond_to(
                html=lambda: self.redirect_to(${singular}_path(self.${singular}), notice="${singular.title()} was successfully created."),
                json=lambda: self.render(json=self.${model_ref})
            )
        else:
            return self.respond_to(
                html=lambda: self.render('new', status=HTTPStatus.UNPROCESSABLE_ENTITY),
                json=lambda: self.render(json=self.${model_ref}.errors, status=HTTPStatus.UNPROCESSABLE_ENTITY)
            )

    def update(self):
        if self.${model_ref}.update(**self._${model_ref}_params()):
            return self.respond_to(
                html=lambda: self.redirect_to(${singular}_path(self.${model_ref}), notice="${singular.title()} was successfully updated."),
                json=lambda: self.render(json=self.${model_ref})
            )
        else:
            return self.respond_to(
                html=lambda: self.render('edit', status=HTTPStatus.UNPROCESSABLE_ENTITY),
                json=lambda: self.render(json=self.${model_ref}.errors, status=HTTPStatus.UNPROCESSABLE_ENTITY)
            )

    def destroy(self):
        self.${model_ref}.destroy()
        return self.respond_to(
            html=lambda: self.redirect_to(${collection}_path(), status=HTTPStatus.SEE_OTHER),
            json=lambda: self.head(HTTPStatus.NO_CONTENT)
        )

    def _set_${model_ref}(self):
        self.${model_ref} = ${model}.find(id=self.params['id'])

    def _${model_ref}_params(self):
        permitted = [${', '.join("'" + field['name'] + "'" for field in fields)}]
% for rich_text in rich_texts:
        permitted.append("${rich_text}")
% endfor
% for attachment in attachments:
        permitted.append(${"('" + attachment['name'] + "', [])" if attachment['type'] == 'attachments' else "'" + attachment['name'] + "'"})
% endfor
        return self.params.expect(${model_ref}=permitted)
