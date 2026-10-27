from http import HTTPStatus

import pytest
from werkzeug.exceptions import HTTPException, TooManyRequests

from flaskteroids.controller import ActionController, init
from flaskteroids.exceptions import ProgrammerError
from flaskteroids.rate_limit import rate_limit


@pytest.fixture(autouse=True)
def req(mocker):
    mock = mocker.Mock()
    mock.remote_addr.return_value = "127.0.0.1"
    mocker.patch("flaskteroids.rate_limit.request", mock)
    return mock


@pytest.fixture()
def rate_limited_controller():

    class TestController(ActionController):
        rate_limit(to=5, within=60)

        def index(self):
            pass

    return init(TestController)


@pytest.mark.usefixtures("app_ctx")
def test_rate_limit_rejects_requests_exceeding_threshold(rate_limited_controller):
    controller = rate_limited_controller()
    controller.index()
    controller.index()
    controller.index()
    controller.index()
    controller.index()
    with pytest.raises(HTTPException) as e:
        controller.index()

    assert e.value.code == HTTPStatus.TOO_MANY_REQUESTS


@pytest.mark.usefixtures("app_ctx")
def test_rate_limit_calls_an_instance_handler_without_requiring_a_response_return():
    events = []

    class LimitedController(ActionController):
        rate_limit(to=1, within=60, using="_exceeded")

        def index(self):
            events.append("action")
            self.head(200)

        def _exceeded(self):
            self.head(429, headers={"Retry-After": "60"})

    controller = init(LimitedController)()
    assert controller.index().status_code == 200
    response = controller.index()
    assert response.status_code == 429
    assert response.headers["Retry-After"] == "60"
    assert events == ["action"]


@pytest.mark.usefixtures("app_ctx")
def test_rate_limit_uses_a_callable_handler_when_the_limit_is_exceeded(mocker):
    handler = mocker.Mock(side_effect=TooManyRequests("Slow down"))

    class LimitedController(ActionController):
        rate_limit(to=1, within=60, using=handler)

        def index(self):
            self.head(200)

    controller = init(LimitedController)()
    assert controller.index().status_code == 200
    handler.assert_not_called()
    with pytest.raises(TooManyRequests, match="Slow down"):
        controller.index()
    handler.assert_called_once_with()


def test_rate_limit_rejects_unknown_instance_handlers():
    class LimitedController(ActionController):
        rate_limit(to=1, within=60, using="_missing")

        def index(self):
            pass

    with pytest.raises(ProgrammerError):
        init(LimitedController)
