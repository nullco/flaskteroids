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
