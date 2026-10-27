import pytest

from flaskteroids.controller import APIController, wrap_parameters
from flaskteroids.exceptions import ProgrammerError


@pytest.mark.parametrize(
    "endpoint,root",
    [
        ("custom_wrappeds", "payload"),
        ("inherited_wrappeds", "payload"),
        ("disabled_wrappeds", None),
        ("restored_wrappeds", "restored_wrapped"),
        ("mixin_wrappeds", "envelope"),
        ("overridden_wrappeds", "final"),
    ],
)
def test_wrapping_declarations_preserve_each_controller_configuration(
    api_client, endpoint, root
):
    response = api_client.post(f"/{endpoint}", json={"title": "Hello"})

    assert response.status_code == 200
    expected = {"title": "Hello"}
    if root is not None:
        expected[root] = {"title": "Hello"}
    assert response.get_json() == expected


def test_browser_controller_accepts_wrapping_declaration(api_application_factory):
    client = api_application_factory(api_only=False).test_client()
    token = client.get("/browser").get_json()["csrf_token"]

    response = client.post(
        "/browser_wrappeds",
        json={"title": "Hello"},
        headers={"X-CSRF-TOKEN": token},
    )

    assert response.status_code == 200
    assert response.get_json() == {
        "title": "Hello",
        "browser": {"title": "Hello"},
    }


@pytest.mark.parametrize("setting", [None, 0, 1, [], {}, "", "   "])
def test_wrapping_declaration_rejects_invalid_settings(setting):
    with pytest.raises(ProgrammerError, match="wrap_parameters"):

        class InvalidController(APIController):
            wrap_parameters(setting)


def test_wrapping_declaration_requires_class_body():
    with pytest.raises(ProgrammerError, match="class body"):
        wrap_parameters(False)
