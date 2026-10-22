from http import HTTPStatus

from flaskteroids import redirect_to
from flaskteroids.actions import before_action
from flaskteroids.controller import ActionController, render, respond
from flaskteroids.helpers import url_for
from tests.app.models.user import User


class UsersController(ActionController):
    before_action("_set_user", only=["show", "edit", "update", "destroy"])

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
                    url_for("show_user", id=self.user.id),
                    notice="User was successfully created.",
                ),
                json=lambda: render(json=self.user),
            )
        else:
            return respond(
                html=lambda: render("new", status=HTTPStatus.UNPROCESSABLE_ENTITY),
                json=lambda: render(
                    json=self.user.errors, status=HTTPStatus.UNPROCESSABLE_ENTITY
                ),
            )

    def edit(self):
        pass

    def update(self):
        if self.user.update(**self._user_params()):
            return respond(
                html=lambda: redirect_to(
                    url_for("show_user", id=self.user.id),
                    notice="User was successfully updated.",
                ),
                json=lambda: render(json=self.user),
            )
        else:
            return respond(
                html=lambda: render("edit", status=HTTPStatus.UNPROCESSABLE_ENTITY),
                json=lambda: render(
                    json=self.user.errors, status=HTTPStatus.UNPROCESSABLE_ENTITY
                ),
            )

    def destroy(self):
        self.user.destroy()

    def _set_user(self):
        self.user = User.find(self.params["id"])

    def _user_params(self):
        return self.params.expect(user=["username"])
