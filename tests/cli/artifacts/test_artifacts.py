import ast

import pytest

from flaskteroids.cli.artifacts import ArtifactsBuilder


@pytest.fixture
def builder(tmp_path, mocker):
    notify = mocker.Mock()
    return ArtifactsBuilder(str(tmp_path), notify), notify


@pytest.mark.parametrize("name", ["test.txt", "nested/test.txt"])
@pytest.mark.parametrize(
    "contents, expected", [(None, ""), ("\n    hello world\n", "hello world\n")]
)
def test_file_creates_parent_directories_and_writes_clean_contents(
    builder, tmp_path, name, contents, expected
):
    instance, notify = builder

    instance.file(name, contents)

    assert (tmp_path / name).read_text() == expected
    notify.assert_called_once()
    assert name in notify.call_args.args[0]


@pytest.mark.parametrize("name", ["bin/start", "scripts/setup.sh"])
def test_file_makes_scripts_executable(builder, tmp_path, name):
    instance, notify = builder

    instance.file(name, "#!/bin/sh\n")

    assert (tmp_path / name).stat().st_mode & 0o111 == 0o111
    notify.assert_called_once()
    assert name in notify.call_args.args[0]


@pytest.mark.parametrize("name", [None, "nested/directory"])
def test_dir_creates_directories_idempotently(builder, tmp_path, name):
    instance, notify = builder
    target = tmp_path / name if name else tmp_path

    instance.dir(name)
    instance.dir(name)

    assert target.is_dir()
    assert notify.call_count == 2


def test_modify_py_file_writes_transformed_source(builder, tmp_path):
    instance, notify = builder
    source = tmp_path / "test.py"
    source.write_text('def hello():\n    return "original"\n')

    class ReplaceGreeting(ast.NodeTransformer):
        def visit_Constant(self, node):
            return ast.copy_location(ast.Constant(value="modified"), node)

    instance.modify_py_file("test.py", ReplaceGreeting)

    assert ast.dump(ast.parse(source.read_text())) == ast.dump(
        ast.parse('def hello():\n    return "modified"\n')
    )
    notify.assert_called_once()
    assert "test.py" in notify.call_args.args[0]
