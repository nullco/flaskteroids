import pytest

from flaskteroids.current import current


@pytest.mark.usefixtures("app_ctx")
def test_current_stores_context_attributes():
    current.attr_one = 1
    assert current.attr_one == 1
