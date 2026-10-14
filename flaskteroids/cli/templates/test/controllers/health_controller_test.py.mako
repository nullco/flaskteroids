from test.test_helper import IntegrationTest, get


class HealthControllerTest(IntegrationTest):
    def test_should_get_health(self):
        get("/up/")

        self.assert_response("success")
