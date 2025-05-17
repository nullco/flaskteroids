from tests.app.models.user import User
from flaskteroids.controller import ActionController


class UsersController(ActionController):

    def index(self):
        self.users = User.all()
