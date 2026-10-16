import io
import time

import pytest
from flask import session as browser_session
from werkzeug.datastructures import MultiDict

from flaskteroids.attachments import Blob, blob_path, blob_url
from flaskteroids.db import session
from tests.attachments.app.models.document import Document


def test_multipart_uploads_reach_strong_parameters(client, app):
    response = client.post(
        "/documents/",
        data={
            "document[title]": "Uploads",
            "document[avatar]": (io.BytesIO(b"\x89PNG\r\n\x1a\nimage"), "avatar.png"),
            "document[files][]": [
                (io.BytesIO(b"first"), "first.txt"),
                (io.BytesIO(b"second"), "second.txt"),
            ],
        },
    )
    assert response.status_code == 200
    assert response.json["errors"] == []
    with app.app_context():
        document = Document.find(response.json["id"])
        assert document.avatar.attached()
        assert [attachment.download() for attachment in document.files] == [
            b"first",
            b"second",
        ]


@pytest.fixture
def download_url(app, upload):
    with app.test_request_context():
        document = Document.create(title="Private", owner_id=7, avatar=upload())
        url = blob_path(document.avatar)
        session.commit()
    return url


def authorize_owner(blob):
    return any(
        attachment.record_type == "Document"
        and Document.find(attachment.record_id).owner_id
        == browser_session.get("user_id")
        for attachment in blob.attachments
    )


def test_signed_blob_links_are_public_and_redirect_to_disk(client, download_url):
    response = client.get(download_url)
    assert response.status_code == 302
    assert "/attachments/disk/" in response.location
    assert response.headers["Cache-Control"] == "private, max-age=300"
    response = client.get(response.location)
    assert response.status_code == 200
    assert response.data == b"\x89PNG\r\n\x1a\nimage"
    assert response.content_type == "image/png"
    assert response.headers["Content-Disposition"].startswith("inline;")
    assert response.headers["X-Content-Type-Options"] == "nosniff"


def test_authorization_is_optional_and_checked_on_blob_routes(
    app, client, download_url
):
    app.config.attachments.authorize = authorize_owner
    assert client.get(download_url).status_code == 404
    with client.session_transaction() as cookie:
        cookie["user_id"] = 8
    assert client.get(download_url).status_code == 404
    with client.session_transaction() as cookie:
        cookie["user_id"] = 7
    response = client.get(download_url)
    assert response.status_code == 302
    assert response.headers["Cache-Control"] == "private, no-store"
    service_url = response.location
    assert client.get(service_url).status_code == 200
    with client.session_transaction() as cookie:
        cookie.clear()
    assert client.get(download_url).status_code == 404
    assert client.get(service_url).status_code == 200


def test_explicit_attachment_disposition_is_preserved(client, download_url):
    response = client.get(
        download_url + "?disposition=attachment", follow_redirects=True
    )
    assert response.status_code == 200
    assert response.content_type == "image/png"
    assert response.headers["Content-Disposition"].startswith("attachment;")


def test_dangerous_types_are_always_served_as_binary_attachments(app, client):
    with app.test_request_context():
        document = Document.create(
            title="HTML",
            files=[
                {
                    "io": io.BytesIO(b"<script>alert('xss')</script>"),
                    "filename": "unsafe.html",
                }
            ],
        )
        url = blob_path(document.files.blobs[0])
        session.commit()
    response = client.get(url, follow_redirects=True)
    assert response.headers["Content-Disposition"].startswith("attachment;")
    assert response.content_type == "application/octet-stream"


def test_permanent_links_outlive_expiring_service_urls(client, download_url, mocker):
    service_url = client.get(download_url).location
    mocker.patch("time.time", return_value=time.time() + 301)
    assert client.get(service_url).status_code == 404
    assert client.get(download_url).status_code == 302
    assert client.get(download_url, follow_redirects=True).status_code == 200


def test_blob_links_can_have_an_explicit_expiration(app, client, download_url, mocker):
    with app.test_request_context():
        url = blob_path(Document.first().avatar, expires_in=1)
    mocker.patch("time.time", return_value=time.time() + 2)
    assert client.get(url).status_code == 404
    assert client.get(download_url).status_code == 302


def test_configured_blob_link_expiration_is_applied_when_generating_links(
    app, client, download_url, mocker
):
    app.config.attachments.urls_expire_in = 1
    with app.test_request_context():
        url = blob_path(Document.first().avatar)
    mocker.patch("time.time", return_value=time.time() + 2)
    assert client.get(url).status_code == 404
    assert client.get(download_url).status_code == 302


def test_signed_blob_ids_work_as_stable_link_tokens(app, client, upload):
    with app.test_request_context():
        document = Document.create(title="Example", avatar=upload())
        url = f"/flaskteroids/attachments/blobs/redirect/{document.avatar.signed_id()}/avatar.png"
        session.commit()
    assert client.get(url, follow_redirects=True).status_code == 200


def test_tampered_blob_and_service_tokens_are_rejected(client, download_url):
    service_url = client.get(download_url).location
    for url in (download_url, service_url):
        parts = url.split("/")
        parts[-2] += "tampered"
        assert client.get("/".join(parts)).status_code == 404


def test_blob_routes_reject_service_tokens(client, download_url):
    service_url = client.get(download_url).location
    parts = download_url.split("/")
    parts[-2] = service_url.split("/")[-2]
    assert client.get("/".join(parts)).status_code == 404


def test_proxy_serves_ranges_and_cacheable_content(app, client, download_url):
    with app.test_request_context():
        proxy = blob_path(Document.first().avatar, route="proxy")
    response = client.get(proxy, headers={"Range": "bytes=0-3"})
    assert response.status_code == 206
    assert response.data == b"\x89PNG"
    assert response.headers["Content-Range"] == "bytes 0-3/13"
    assert response.headers["Accept-Ranges"] == "bytes"
    assert response.headers["Cache-Control"].startswith("public,")
    full = client.get(proxy)
    assert len(full.data) == 13
    assert (
        client.get(proxy, headers={"If-None-Match": full.headers["ETag"]}).status_code
        == 304
    )
    assert client.head(proxy).data == b""


def test_authenticated_proxy_checks_every_request_and_disables_shared_caching(
    app, client, download_url
):
    app.config.attachments.authorize = authorize_owner
    with app.test_request_context():
        url = blob_path(Document.first().avatar, route="proxy")
    assert client.get(url).status_code == 404
    with client.session_transaction() as cookie:
        cookie["user_id"] = 7
    response = client.get(url)
    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "private, no-store"
    with client.session_transaction() as cookie:
        cookie.clear()
    assert client.get(url).status_code == 404


def test_permanent_blob_links_are_identical_when_generated_later(
    app, download_url, mocker
):
    with app.test_request_context():
        document = Document.first()
        first = blob_path(document.avatar)
        mocker.patch("time.time", return_value=time.time() + 1000)
        assert blob_path(document.avatar) == first


def test_proxy_configuration_controls_route_and_absolute_url(app, download_url):
    app.config.attachments.resolve_model_to_route = "proxy"
    with app.test_request_context():
        document = Document.first()
        assert "/blobs/proxy/" in blob_path(document.avatar)
        assert blob_url(document.avatar).startswith("http://localhost/")
        assert "/disk/" in document.avatar.url()


def test_invalid_disposition_returns_bad_request(client, download_url):
    assert client.get(download_url + "?disposition=invalid").status_code == 400


def test_blob_routes_reject_links_to_purged_blobs(app, client, download_url):
    with app.app_context():
        Document.first().avatar.purge()
    assert client.get(download_url).status_code == 404
    with app.app_context():
        Document.create(
            title="Replacement",
            avatar={
                "io": io.BytesIO(b"\x89PNG\r\n\x1a\nreplacement"),
                "filename": "avatar.png",
            },
        )
    assert client.get(download_url).status_code == 404


def test_upload_over_optional_limit_returns_413(app, client):
    app.config.attachments.max_upload_size = 4
    response = client.post(
        "/documents/",
        data={
            "document[title]": "Too big",
            "document[avatar]": (io.BytesIO(b"12345"), "file.png"),
            "document[files][]": "",
        },
    )
    assert response.status_code == 413
    with app.app_context():
        assert Document.count() == 0


def test_retained_blob_ids_are_merged_with_multiple_uploads(app, client, upload):
    with app.test_request_context():
        existing = Document.create(title="Existing", files=[upload(b"old", "old.txt")])
        signed_id = existing.files.blobs[0].signed_id()
        session.commit()
    response = client.post(
        "/documents/",
        data=MultiDict(
            [
                ("document[title]", "New"),
                (
                    "document[avatar]",
                    (io.BytesIO(b"\x89PNG\r\n\x1a\nimage"), "avatar.png"),
                ),
                ("document[files][]", signed_id),
                ("document[files][]", (io.BytesIO(b"new"), "new.txt")),
            ]
        ),
    )
    assert response.status_code == 200
    with app.app_context():
        assert [attachment.download() for attachment in Document.last().files] == [
            b"old",
            b"new",
        ]


def test_upload_failure_after_commit_preserves_metadata(app, client, storage, mocker):
    app.config["PROPAGATE_EXCEPTIONS"] = True
    with app.app_context():
        service = storage.service()
    attempted = []

    def fail(key, data, **options):
        attempted.append(key)
        raise OSError("Storage unavailable")

    mocker.patch.object(service, "upload", side_effect=fail)
    with pytest.raises(OSError, match="Storage unavailable"):
        client.post(
            "/documents/",
            data={
                "document[title]": "Committed",
                "document[avatar]": (
                    io.BytesIO(b"\x89PNG\r\n\x1a\nimage"),
                    "avatar.png",
                ),
                "document[files][]": "",
            },
        )
    assert attempted
    assert not service.exist(attempted[0])
    with app.app_context():
        assert Document.count() == 1
        assert Document.first().avatar.blob.key == attempted[0]


def test_missing_file_redirects_then_returns_not_found(app, client, download_url):
    with app.app_context():
        blob = Document.first().avatar.blob
        blob.service.delete(blob.key)
    assert client.get(download_url).status_code == 302
    assert client.get(download_url, follow_redirects=True).status_code == 404


def test_standalone_upload_survives_later_database_rollback(app, client):
    with app.test_request_context(), Document.transaction():
        blob = Blob.create_and_upload(io=io.BytesIO(b"report"), filename="report.txt")
        service_url = blob.url()
        url = blob_path(blob)
        session.rollback()
    assert client.get(service_url).data == b"report"
    assert client.get(url).status_code == 404
