from test.test_helper import IntegrationTest, get
from flaskteroids.routes import new_session_path


class SessionsControllerTest(IntegrationTest):
    def test_should_get_new(self):
        get(new_session_path())

        self.assert_response("success")
