import pytest

from flaskteroids import discovery
from flaskteroids.extensions import utils


@pytest.mark.parametrize(
    "discover", [discovery.discover_classes, utils.discover_classes]
)
def test_ordinary_discovery_through_both_import_paths(discovery_package, discover):
    name = discovery_package(
        {
            "__init__.py": "",
            "records.py": "class Post: pass\nAlias = Post\nclass Comment: pass\n",
        }
    )
    entries = discover(name, object)
    assert list(entries) == ["Alias", "Comment", "Post"]
    assert entries["Alias"].__name__ == entries["Post"].__name__ == "Post"
    assert list(discover(name, object, ignore={"Comment"})) == ["Alias", "Post"]


@pytest.mark.parametrize(
    "discover", [discovery.discover_classes, utils.discover_classes]
)
def test_absent_package_through_both_import_paths(discovery_package, discover):
    name = discovery_package({})
    assert discover(f"{name}.jobs", object) == {}


@pytest.mark.parametrize(
    "discover", [discovery.discover_classes, utils.discover_classes]
)
@pytest.mark.parametrize("location", ["__init__.py", "child.py"])
def test_broken_package_through_both_import_paths(
    discovery_package, discover, location
):
    name = discovery_package(
        {"__init__.py": "", location: "import phase5_missing_dependency"}
    )
    with pytest.raises(ModuleNotFoundError) as raised:
        discover(name, object)
    assert raised.value.name == "phase5_missing_dependency"


@pytest.mark.parametrize(
    "discover", [discovery.discover_methods, utils.discover_methods]
)
def test_method_selection_through_both_import_paths(discover):
    class Example:
        def zebra(self):
            pass

        def alpha(self):
            pass

        def _private(self):
            pass

        @property
        def value(self):
            return "value"

    assert discover(Example) == ["alpha", "zebra"]
    assert discover(Example, ignore={"zebra"}) == ["alpha"]
