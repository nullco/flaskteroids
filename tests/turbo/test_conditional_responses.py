import pytest
from flask import Response, current_app, request
from jinja2 import DictLoader

from flaskteroids.controller import ActionController, init


class ConditionalController(ActionController):
    def rendered(self):
        self.response.set_etag("version-1", weak="weak" in request.args)
        self.render("conditional/show")
        self.response.make_conditional(request)

    def framework(self):
        response = current_app.response_class("Framework response")
        response.set_etag("version-1", weak="weak" in request.args)
        return response.make_conditional(request)

    def native(self):
        response = Response("Native response")
        response.set_etag("native-version")
        return response.make_conditional(request)

    def late(self):
        self.render("conditional/show")


@pytest.fixture
def conditional_app(view_app_factory):
    app = view_app_factory(owners=False)
    app.jinja_loader = DictLoader(
        {"conditional/show.html": "{{ turbo_frame_request_id() or 'full page' }}"}
    )
    init(ConditionalController)
    for mode in ("rendered", "framework", "native", "late"):
        app.add_url_rule(
            f"/conditional/{mode}",
            endpoint=mode,
            view_func=lambda mode=mode: getattr(ConditionalController(), mode)(),
        )

    @app.after_request
    def application_conditional(response):
        if request.endpoint == "late":
            response.set_etag("late-version")
            response.make_conditional(request)
        return response

    return app


@pytest.mark.parametrize("mode", ["rendered", "framework", "late"])
@pytest.mark.parametrize("frame", [False, True])
@pytest.mark.parametrize("weak", [False, True])
def test_same_variant_supports_conditional_revalidation(
    conditional_app, mode, frame, weak
):
    client = conditional_app.test_client()
    path = f"/conditional/{mode}" + ("?weak=1" if weak else "")
    headers = {"Turbo-Frame": "editor"} if frame else {}
    first = client.get(path, headers=headers)
    repeated = client.get(
        path, headers={**headers, "If-None-Match": first.headers["ETag"]}
    )
    assert first.status_code == 200
    assert repeated.status_code == 304
    assert repeated.data == b""
    assert repeated.headers["ETag"] == first.headers["ETag"]


@pytest.mark.parametrize("mode", ["rendered", "framework", "late"])
@pytest.mark.parametrize("frame", [False, True])
def test_same_variant_strong_preconditions_accept_the_published_etag(
    conditional_app, mode, frame
):
    client = conditional_app.test_client()
    headers = {"Turbo-Frame": "editor"} if frame else {}
    path = f"/conditional/{mode}"
    etag = client.get(path, headers=headers).headers["ETag"]
    response = client.get(path, headers={**headers, "If-Match": etag})
    assert response.status_code == 200


@pytest.mark.parametrize("mode", ["rendered", "framework", "late"])
@pytest.mark.parametrize("frame_first", [False, True])
def test_conditional_validators_distinguish_frames_from_full_pages(
    conditional_app, mode, frame_first
):
    client = conditional_app.test_client()
    path = f"/conditional/{mode}"
    original_headers = {"Turbo-Frame": "editor"} if frame_first else {}
    other_headers = {} if frame_first else {"Turbo-Frame": "editor"}
    etag = client.get(path, headers=original_headers).headers["ETag"]
    response = client.get(path, headers={**other_headers, "If-None-Match": etag})
    assert response.status_code == 200
    assert response.headers["ETag"] != etag
    precondition = client.get(path, headers={**other_headers, "If-Match": etag})
    assert precondition.status_code == 412


@pytest.mark.parametrize("frame", [False, True])
def test_native_response_validators_remain_owned_by_the_application(
    conditional_app, frame
):
    client = conditional_app.test_client()
    path = "/conditional/native"
    headers = {"Turbo-Frame": "editor"} if frame else {}
    first = client.get(path, headers=headers)
    assert first.get_etag() == ("native-version", False)
    assert (
        client.get(
            path, headers={**headers, "If-None-Match": first.headers["ETag"]}
        ).status_code
        == 304
    )
    assert (
        client.get(
            path, headers={**headers, "If-Match": first.headers["ETag"]}
        ).status_code
        == 200
    )


def test_custom_response_classes_keep_their_behavior(conditional_app):
    base = conditional_app.response_class

    class ApplicationResponse(base):
        custom_behavior = "retained"

    conditional_app.response_class = ApplicationResponse
    response = conditional_app.test_client().get("/conditional/framework")
    assert response.custom_behavior == "retained"
    assert response.status_code == 200
