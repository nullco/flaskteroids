from test.test_helper import IntegrationTest, get


class ${name}ControllerTest(IntegrationTest):
% for action in actions:
    def test_should_get_${action}(self):
        get("/${path}/${action}")

        self.assert_response("success")

% endfor
% if not actions:
    pass
% endif
