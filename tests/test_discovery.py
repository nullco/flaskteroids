import pytest

from flaskteroids.discovery import discover_classes


@pytest.mark.parametrize("suffix", ["", ".app", ".app.jobs"])
def test_absent_optional_package(discovery_package, suffix):
    name = discovery_package({})
    assert discover_classes(name + suffix, object) == {}


@pytest.mark.parametrize(
    "files",
    [
        {"__init__.py": ""},
        {"__init__.py": "", "app/__init__.py": ""},
    ],
)
def test_absent_leaf_package(discovery_package, files):
    name = discovery_package(files)
    assert discover_classes(f"{name}.app.jobs", object) == {}


def test_empty_package(discovery_package):
    name = discovery_package({"__init__.py": ""})
    assert discover_classes(name, object) == {}


def test_discovery_and_ignore(discovery_package):
    name = discovery_package(
        {
            "__init__.py": "",
            "records.py": "class Post: pass\nclass Comment: pass\n",
        }
    )
    assert set(discover_classes(name, object)) == {"Post", "Comment"}
    assert set(discover_classes(name, object, ignore={"Comment"})) == {"Post"}


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


def test_child_import_is_not_optional(discovery_package):
    name = discovery_package(
        {
            "__init__.py": "",
            "child.py": "raise ModuleNotFoundError('broken child', name=__name__)",
        }
    )
    with pytest.raises(ModuleNotFoundError) as raised:
        discover_classes(name, object)
    assert raised.value.name == f"{name}.child"


def test_undotted_prefix_is_not_an_absent_ancestor(discovery_package):
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


def test_configured_module_must_be_a_package(discovery_package):
    name = discovery_package({"__init__.py": "", "module.py": ""})
    with pytest.raises(AttributeError, match="__path__"):
        discover_classes(f"{name}.module", object)
