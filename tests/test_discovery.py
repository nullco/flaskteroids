import pytest

from flaskteroids.discovery import discover_classes, discover_methods


@pytest.mark.parametrize("suffix", ["", ".app", ".app.jobs"])
def test_discovery_returns_empty_results_for_absent_optional_packages(
    discovery_package, suffix
):
    name = discovery_package({})
    assert discover_classes(name + suffix, object) == {}


@pytest.mark.parametrize(
    "files",
    [
        {"__init__.py": ""},
        {"__init__.py": "", "app/__init__.py": ""},
    ],
)
def test_discovery_returns_empty_results_for_absent_leaf_packages(
    discovery_package, files
):
    name = discovery_package(files)
    assert discover_classes(f"{name}.app.jobs", object) == {}


def test_discovery_returns_empty_results_for_empty_packages(discovery_package):
    name = discovery_package({"__init__.py": ""})
    assert discover_classes(name, object) == {}


def test_discovery_orders_classes_and_applies_ignore_filter(discovery_package):
    name = discovery_package(
        {
            "__init__.py": "",
            "records.py": "class Post: pass\nAlias = Post\nclass Comment: pass\n",
        }
    )
    entries = discover_classes(name, object)
    assert list(entries) == ["Alias", "Comment", "Post"]
    assert entries["Alias"] is entries["Post"]
    assert list(discover_classes(name, object, ignore={"Comment"})) == ["Alias", "Post"]


@pytest.mark.parametrize("location", ["__init__.py", "child.py"])
@pytest.mark.parametrize(
    "dependency", ["phase4_missing_driver", ".adapter", ".sibling"]
)
def test_dependency_failures_propagate(discovery_package, location, dependency):
    if dependency.startswith("."):
        source = f"from importlib import import_module\nimport_module(__package__ + {dependency!r})\n"
    else:
        source = f"import {dependency}\n"
    name = discovery_package({"__init__.py": "", location: source})
    expected = name + dependency if dependency.startswith(".") else dependency
    with pytest.raises(ModuleNotFoundError) as raised:
        discover_classes(name, object)
    assert raised.value.name == expected


@pytest.mark.parametrize("missing_name", [None, "", 123, "unrelated", "child"])
def test_unusable_or_unrelated_missing_names_propagate(discovery_package, missing_name):
    name = discovery_package(
        {
            "__init__.py": f"raise ModuleNotFoundError('broken', name={missing_name!r})",
        }
    )
    with pytest.raises(ModuleNotFoundError):
        discover_classes(name, object)


def test_discovery_propagates_missing_child_imports(discovery_package):
    name = discovery_package(
        {
            "__init__.py": "",
            "child.py": "raise ModuleNotFoundError('broken child', name=__name__)",
        }
    )
    with pytest.raises(ModuleNotFoundError) as raised:
        discover_classes(name, object)
    assert raised.value.name == f"{name}.child"


def test_discovery_propagates_errors_with_undotted_name_prefixes(discovery_package):
    name = discovery_package(
        {
            "__init__.py": "raise ModuleNotFoundError('broken', name=__name__[:-1])",
        }
    )
    with pytest.raises(ModuleNotFoundError) as raised:
        discover_classes(name, object)
    assert raised.value.name == name[:-1]


@pytest.mark.parametrize("location", ["__init__.py", "child.py"])
@pytest.mark.parametrize(
    "source, error",
    [
        ("raise ImportError('broken')", ImportError),
        ("def broken(:", SyntaxError),
    ],
)
def test_other_import_failures_propagate(discovery_package, location, source, error):
    name = discovery_package({"__init__.py": "", location: source})
    with pytest.raises(error):
        discover_classes(name, object)


def test_discovery_rejects_configured_modules_that_are_not_packages(discovery_package):
    name = discovery_package({"__init__.py": "", "module.py": ""})
    with pytest.raises(AttributeError, match="__path__"):
        discover_classes(f"{name}.module", object)


def test_method_discovery_selects_public_methods_and_applies_ignore_filter():
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

    assert discover_methods(Example) == ["alpha", "zebra"]
    assert discover_methods(Example, ignore={"zebra"}) == ["alpha"]
