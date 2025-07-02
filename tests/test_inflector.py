import pytest
from flaskteroids.inflector import Inflector


@pytest.fixture
def inflector():
    return Inflector()


def test_pluralize(inflector):
    assert inflector.pluralize("cat") == "cats"
    assert inflector.pluralize("person") == "people"
    assert inflector.pluralize("Person") == "People"
    assert inflector.pluralize("sheep") == "sheep"
    assert inflector.pluralize("box") == "boxes"
    assert inflector.pluralize("query") == "queries"


def test_singularize(inflector):
    assert inflector.singularize("cats") == "cat"
    assert inflector.singularize("people") == "person"
    assert inflector.singularize("People") == "Person"
    assert inflector.singularize("sheep") == "sheep"
    assert inflector.singularize("boxes") == "box"
    assert inflector.singularize("queries") == "query"


def test_underscore(inflector):
    assert inflector.underscore("UserProfile") == "user_profile"
    assert inflector.underscore("APIClient") == "api_client"
    assert inflector.underscore("SomeHTTPResponse") == "some_http_response"


def test_camelize(inflector):
    assert inflector.camelize("user_profile") == "UserProfile"
    assert inflector.camelize("api_client") == "ApiClient"
    assert inflector.camelize("some_http_response") == "SomeHttpResponse"
    assert inflector.camelize("user_profile", uppercase_first_letter=False) == "userProfile"


def test_tableize(inflector):
    assert inflector.tableize("UserProfile") == "user_profiles"
    assert inflector.tableize("Category") == "categories"


def test_classify(inflector):
    assert inflector.classify("user_profiles") == "UserProfile"
    assert inflector.classify("categories") == "Category"


def test_foreign_key(inflector):
    assert inflector.foreign_key("User") == "user_id"
    assert inflector.foreign_key("UserProfile") == "user_profile_id"


def test_different_locale(inflector):
    # Test default English rules
    assert inflector.pluralize("cat") == "cats"

    # Add a Spanish plural rule (example: add 'es' to words ending in 'z')
    inflector.add_plural_rule(r"([aeiou])z$", r"\1ces", locale="es")
    inflector.add_plural_rule(r"$", r"s", locale="es")  # Default Spanish plural
    inflector.add_irregular("el", "los", locale="es")

    assert inflector.pluralize("pez", locale="es") == "peces"
    assert inflector.pluralize("gato", locale="es") == "gatos"
    assert inflector.pluralize("el", locale="es") == "los"

    # Corrected assertion: English rules apply, so "pez" becomes "pezes"
    assert inflector.pluralize("pez") == "pezes"
    assert inflector.pluralize("cat") == "cats"

    # Test pluralize with explicit locale argument
    assert inflector.pluralize("pez", locale="es") == "peces"
    assert inflector.pluralize("cat", locale="en") == "cats"
