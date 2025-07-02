import pytest
from flaskteroids.inflector import Inflector


@pytest.fixture
def inflector():
    return Inflector()


@pytest.mark.parametrize("word, expected", [
    ("cat", "cats"),
    ("person", "people"),
    ("Person", "People"),
    ("sheep", "sheep"),
    ("box", "boxes"),
    ("query", "queries"),
])
def test_pluralize(inflector, word, expected):
    assert inflector.pluralize(word) == expected


@pytest.mark.parametrize("word, expected", [
    ("cats", "cat"),
    ("people", "person"),
    ("People", "Person"),
    ("sheep", "sheep"),
    ("boxes", "box"),
    ("queries", "query"),
])
def test_singularize(inflector, word, expected):
    assert inflector.singularize(word) == expected


@pytest.mark.parametrize("word, expected", [
    ("UserProfile", "user_profile"),
    ("APIClient", "api_client"),
    ("SomeHTTPResponse", "some_http_response"),
])
def test_underscore(inflector, word, expected):
    assert inflector.underscore(word) == expected


@pytest.mark.parametrize("word, uppercase_first, expected", [
    ("user_profile", True, "UserProfile"),
    ("api_client", True, "ApiClient"),
    ("some_http_response", True, "SomeHttpResponse"),
    ("user_profile", False, "userProfile"),
])
def test_camelize(inflector, word, uppercase_first, expected):
    assert inflector.camelize(word, uppercase_first_letter=uppercase_first) == expected


@pytest.mark.parametrize("class_name, expected", [
    ("UserProfile", "user_profiles"),
    ("Category", "categories"),
])
def test_tableize(inflector, class_name, expected):
    assert inflector.tableize(class_name) == expected


@pytest.mark.parametrize("table_name, expected", [
    ("user_profiles", "UserProfile"),
    ("categories", "Category"),
])
def test_classify(inflector, table_name, expected):
    assert inflector.classify(table_name) == expected


@pytest.mark.parametrize("class_name, expected", [
    ("User", "user_id"),
    ("UserProfile", "user_profile_id"),
])
def test_foreign_key(inflector, class_name, expected):
    assert inflector.foreign_key(class_name) == expected


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
