from test.test_helper import IntegrationTest, get
from flaskteroids.routes import new_password_path


class PasswordsControllerTest(IntegrationTest):
    def test_should_get_new(self):
        get(new_password_path())

        self.assert_response("success")
