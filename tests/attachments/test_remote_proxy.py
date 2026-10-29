import io

import pytest

from flaskteroids.attachments import Blob, blob_path


class ChunkedBody(io.BytesIO):
    def read(self, size=-1):
        assert 0 <= size <= 64 * 1024
        return super().read(size)


@pytest.fixture
def remote_blob(app, remote_service):
    data = b"remote file contents\n" * 10000
    remote_service.stream_class = ChunkedBody
    with app.test_request_context():
        blob = Blob.create_and_upload(
            io=io.BytesIO(data), filename="report.txt", service_name="remote"
        )
        url = blob_path(blob, route="proxy")
    return url, remote_service, data, blob.key


def test_remote_proxy_reads_bounded_chunks_and_closes_the_body(client, remote_blob):
    url, service, data, _key = remote_blob
    response = client.get(url)
    assert response.status_code == 200
    assert response.data == data
    assert response.content_length == len(data)
    assert response.headers["Accept-Ranges"] == "bytes"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["Content-Disposition"].startswith("attachment;")
    response.close()
    assert service.bodies[0].closed
    assert service.ranges == [(None, None)]


@pytest.mark.parametrize(
    "header, start, length",
    [("bytes=0-3", 0, 4), ("bytes=7-", 7, None), ("bytes=-4", None, 4)],
)
def test_remote_proxy_fetches_only_the_requested_range(
    client, remote_blob, header, start, length
):
    url, service, data, _key = remote_blob
    start = len(data) - length if start is None else start
    length = len(data) - start if length is None else length
    end = start + length - 1
    response = client.get(url, headers={"Range": header})
    assert response.status_code == 206
    assert response.data == data[start : end + 1]
    assert response.content_length == length
    assert response.headers["Content-Range"] == f"bytes {start}-{end}/{len(data)}"
    assert service.ranges == [(start, end)]
    response.close()
    assert service.bodies[0].closed


def test_remote_proxy_answers_head_and_not_modified_from_metadata(client, remote_blob):
    url, service, data, _key = remote_blob
    response = client.head(url)
    assert response.status_code == 200
    assert response.data == b""
    assert response.content_length == len(data)
    etag = response.headers["ETag"]
    response = client.get(url, headers={"If-None-Match": etag})
    assert response.status_code == 304
    assert response.data == b""
    assert not service.ranges
    assert not service.bodies


def test_remote_proxy_rejects_invalid_range_before_download(client, remote_blob):
    url, service, data, _key = remote_blob
    response = client.get(url, headers={"Range": f"bytes={len(data)}-"})
    assert response.status_code == 416
    assert not service.ranges
    assert not service.bodies


def test_remote_proxy_if_range_controls_partial_downloads(client, remote_blob):
    url, service, data, _key = remote_blob
    etag = client.head(url).headers["ETag"]
    response = client.get(url, headers={"Range": "bytes=0-3", "If-Range": etag})
    assert response.status_code == 206
    assert response.data == data[:4]
    response.close()
    response = client.get(url, headers={"Range": "bytes=0-3", "If-Range": '"other"'})
    assert response.status_code == 200
    assert response.data == data
    assert service.ranges == [(0, 3), (None, None)]
    response.close()
    assert all(body.closed for body in service.bodies)


def test_remote_proxy_closes_an_abandoned_response(client, remote_blob):
    url, service, _data, _key = remote_blob
    response = client.get(url, buffered=False)
    assert response.status_code == 200
    response.close()
    assert service.bodies[0].closed


def test_missing_remote_file_returns_not_found(client, remote_blob):
    url, service, _data, key = remote_blob
    service.delete(key)
    assert client.get(url).status_code == 404
    assert not service.bodies
