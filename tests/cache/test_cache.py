from flaskteroids import cache


def test_cache(mocker):
    mock = mocker.Mock()

    @cache.value('my-key', ttl=30)
    def expensive_call():
        mock.call()
        return 12345

    mock.call.assert_not_called()
    value = expensive_call()
    assert value == 12345
    value = expensive_call()
    assert value == 12345
    assert mock.call.call_count == 1
