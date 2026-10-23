[project]
name = ${project_name_toml}
version = "0.1.0"
description = "Add your description here"
readme = "README.md"
requires-python = ">=3.12"
dependencies = [
    ${framework_dependency_toml},
    "gunicorn",
]

[tool.uv]
package = false
% if framework_path_toml:

[tool.uv.sources]
flaskteroids = { path = ${framework_path_toml}, editable = true }
% endif

[tool.pytest.ini_options]
testpaths = ["test"]
python_files = ["*_test.py"]
python_classes = ["*Test"]
python_functions = ["test_*"]
