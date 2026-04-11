import pytest
from cucurbit.current import current


@pytest.mark.usefixtures('app_ctx')
def test_store():
    current.attr_one = 1
    assert current.attr_one == 1
