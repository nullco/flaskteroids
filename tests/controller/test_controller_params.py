import pytest

from flaskteroids.actions import after_action, before_action
from flaskteroids.controller import Controller, init


class InputsController(Controller):
    before_action("_read_before")
    after_action("_read_after")

    def _read_before(self):
        self.before_value = self.params["value"]

    def show(self):
        self.filtered = self.params.expect(item=["name"])
        self.params["action_seen"] = True

    def _read_after(self):
        self.after_value = self.params["value"]


@pytest.mark.usefixtures("app_ctx")
def test_controller_instances_own_independent_parameter_maps():
    first = Controller()
    first.params["value"] = "First"
    second = Controller()
    second.params["value"] = "Second"
    assert first.params == {"value": "First"}
    assert second.params == {"value": "Second"}


@pytest.mark.usefixtures("app_ctx")
def test_callbacks_actions_and_rendering_share_controller_params(render_template):
    controller = init(InputsController)()
    controller.params.update(value="Reader", item={"name": "Allowed", "admin": True})
    controller.show()
    render_template.assert_called_once_with(
        "inputs/show.html",
        before_value="Reader",
        filtered={"name": "Allowed"},
        params=controller.params,
    )
    assert controller.params["action_seen"] is True
    assert controller.after_value == "Reader"
