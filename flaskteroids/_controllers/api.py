"""Controllers with explicit rendering and no browser presentation defaults."""

from flaskteroids._controllers.base import ControllerBase, prepare_controller
from flaskteroids._request_policy import API_REQUESTS


class APIController(ControllerBase):
    _request_policy = API_REQUESTS

    @classmethod
    def _flaskteroids_prepare(cls):
        return prepare_controller(cls, APIController)

    def _default_render(self):
        return self.head(204)
