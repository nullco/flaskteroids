import pytest

from tests.turbo.fixtures.records import Post
from tests.views.conftest import view_app_factory as view_app_factory


@pytest.fixture
def post():
    return Post(1)
