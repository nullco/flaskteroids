import flaskteroids.cli.artifacts as artifacts
from flaskteroids.cli.artifacts import ArtifactsBuilder, ArtifactsBuilderException
import pytest


@pytest.fixture(autouse=True)
def subprocess(mocker):
    subprocess = mocker.patch.object(artifacts, 'subprocess')
    res = mocker.Mock()
    res.returncode = 0
    subprocess.run.return_value = res
    return subprocess


@pytest.fixture(autouse=True)
def os(mocker):
    os = mocker.patch.object(artifacts, 'os')
    return os


@pytest.fixture
def builder():
    return ArtifactsBuilder('.')


@pytest.fixture(autouse=True)
def path(mocker):
    Path = mocker.patch.object(artifacts, 'Path')
    return Path


def test_create_file(builder):
    builder.file('test.txt')


def test_create_dir(builder):
    builder.file('test/')


def test_run(builder):
    builder.run('ls -la')


def test_run_fails(builder, subprocess):
    subprocess.run.return_value.returncode = -1
    with pytest.raises(ArtifactsBuilderException):
        builder.run('ls -la')


def test_create_file_with_contents(builder):
    builder.file('test.txt', 'hello world')


def test_dir_without_name(builder):
    builder.dir()


def test_python_run(builder):
    builder.python_run('pip install something')


def test_python_run_fails(builder, subprocess):
    subprocess.run.return_value.returncode = -1
    with pytest.raises(ArtifactsBuilderException):
        builder.python_run('pip install something')


def test_modify_py_file(builder, mocker):
    mocker.patch('builtins.open', mocker.mock_open(read_data='def hello():\n    pass\n'))
    mock_parse = mocker.patch('flaskteroids.cli.artifacts.ast.parse')
    mock_tree = mocker.Mock()
    mock_parse.return_value = mock_tree
    mocker.patch('flaskteroids.cli.artifacts.ast.unparse', return_value='def hello():\n    print("modified")\n')

    def visitor():
        visitor.visit = lambda tree: tree
        return visitor

    builder.modify_py_file('test.py', visitor)
