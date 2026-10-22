import pytest
from flask import render_template_string

from flaskteroids.exceptions import ProgrammerError


@pytest.mark.parametrize("suffix", [".absent", ".absent.helpers"])
def test_absent_helper_packages_allow_rendering(
    view_app_factory, discovery_package, suffix
):
    package = discovery_package({"__init__.py": ""})
    app = view_app_factory(helpers=package + suffix, owners=False)

    with app.app_context():
        assert render_template_string("{{ greeting is defined }}") == "False"


@pytest.mark.parametrize(
    "location", ["__init__.py", "format_helper.py", "admin/__init__.py"]
)
@pytest.mark.parametrize(
    "source, error",
    [
        ("import missing_helper_dependency", ModuleNotFoundError),
        ("raise ImportError('broken helper import')", ImportError),
        ("def broken(:", SyntaxError),
        ("raise ModuleNotFoundError('broken', name=__name__)", ModuleNotFoundError),
    ],
)
def test_existing_helper_import_failures_stop_boot(
    view_app_factory, discovery_package, location, source, error
):
    files = {
        "__init__.py": "",
        "admin/format_helper.py": "class FormatHelper: pass",
    }
    files[location] = source
    package = discovery_package(files)

    with pytest.raises(error):
        view_app_factory(helpers=package, owners=False)


def test_configured_helper_modules_must_be_packages(
    view_app_factory, discovery_package
):
    package = discovery_package({"__init__.py": "", "helpers.py": ""})

    with pytest.raises(ProgrammerError, match="must name a package"):
        view_app_factory(helpers=package + ".helpers", owners=False)


@pytest.mark.parametrize(
    "source",
    [
        "class WrongHelper: pass",
        "FormatHelper = object()",
        "from pathlib import Path as FormatHelper",
    ],
)
def test_helper_files_must_define_their_conventional_classes(
    view_app_factory, discovery_package, source
):
    package = discovery_package({"__init__.py": "", "format_helper.py": source})

    with pytest.raises(ProgrammerError, match="must define FormatHelper"):
        view_app_factory(helpers=package, owners=False)


def test_helper_mixins_reject_constructors(view_app_factory, discovery_package):
    package = discovery_package(
        {
            "__init__.py": "",
            "format_helper.py": "class FormatHelper:\n    def __init__(self): pass",
        }
    )

    with pytest.raises(ProgrammerError, match="cannot define __init__"):
        view_app_factory(helpers=package, owners=False)
