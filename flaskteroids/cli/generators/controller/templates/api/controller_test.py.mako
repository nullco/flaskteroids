from test.test_helper import IntegrationTest, get


class ${name}ControllerTest(IntegrationTest):
% for action in actions:
    def test_${action}_returns_no_content(self):
        get("/${path}/${action}")

        self.assert_response(204)

% endfor
% if not actions:
    pass
% endif
