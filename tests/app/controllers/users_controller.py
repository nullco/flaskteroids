from http import HTTPStatus
from tests.app.models.user import User
from flaskteroids import redirect_to
from flaskteroids.helpers import url_for
from flaskteroids.rules import rules
from flaskteroids.actions import params, before_action
from flaskteroids.controller import ActionController, respond, render


@rules(
    before_action('_set_user', only=['show', 'edit', 'update', 'destroy'])
)
class UsersController(ActionController):

    def index(self):
        self.users = User.all()

    def show(self):
        pass

    def new(self):
        self.user = User.new()

    def create(self):
        self.user = User.create(**self._user_params())
        if self.user.save():
            return respond(
                html=lambda: redirect_to(
                    url_for('show_user', id=self.user.id),
                    notice="User was successfully created."
                ),
                json=lambda: render(json=self.user)
            )
        else:
            return respond(
                html=lambda: render('new', status=HTTPStatus.UNPROCESSABLE_ENTITY),
                json=lambda: render(json=self.user.errors, status=HTTPStatus.UNPROCESSABLE_ENTITY)
            )

    def edit(self):
        pass

    def update(self):
        if self.user.update(**self._user_params()):
            return respond(
                html=lambda: redirect_to(
                    url_for('show_user', id=self.user.id),
                    notice="User was successfully updated."
                ),
                json=lambda: render(json=self.user)
            )
        else:
            return respond(
                html=lambda: render('edit', status=HTTPStatus.UNPROCESSABLE_ENTITY),
                json=lambda: render(json=self.user.errors, status=HTTPStatus.UNPROCESSABLE_ENTITY)
            )

    def destroy(self):
        self.user.destroy()

    def _set_user(self):
        self.user = User.find(params['id'])

    def _user_params(self):
        return params.expect(user=['username'])
