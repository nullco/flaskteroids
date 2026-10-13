import os
from pathlib import Path

import yaml
from flask import Blueprint, abort, current_app, redirect, request, send_file
from itsdangerous import BadSignature
from werkzeug.wsgi import wrap_file

from flaskteroids.attachments.blob import Blob
from flaskteroids.attachments.filenames import content_disposition
from flaskteroids.attachments.services import DiskService, S3Service, StorageError
from flaskteroids.attachments.signatures import verified_token
from flaskteroids.exceptions import ProgrammerError, RecordNotFoundException


class AttachmentsExtension:
    def __init__(self, app):
        self.init_app(app)

    def init_app(self, app):
        if getattr(self, "_app", app) is not app:
            raise ProgrammerError(
                "An attachments extension cannot be shared between applications."
            )
        if "flaskteroids.attachments" in app.extensions:
            return
        self.service_name = app.config.attachments.service or (
            "test" if app.env.test else "local"
        )
        self.root = app.project_root
        path = self.root / "config" / "storage.yml"
        if path.exists():
            self.configurations = yaml.safe_load(path.read_text()) or {}
        else:
            self.configurations = {
                "local": {"service": "Disk", "root": "storage"},
                "test": {"service": "Disk", "root": "tmp/storage"},
            }
        if not isinstance(self.configurations, dict):
            raise StorageError("config/storage.yml must contain a mapping")
        self.services = {}
        if app.config.attachments.draw_routes:
            self._register_routes(app)
        self._app = app
        app.extensions["flaskteroids.attachments"] = self

    def service(self, name=None):
        name = name or self.service_name
        if name not in self.services:
            configuration = self.configurations.get(name)
            if not isinstance(configuration, dict):
                raise StorageError(
                    f"Storage service {name!r} was not found in config/storage.yml"
                )
            options = {
                key: self._resolve(value) for key, value in configuration.items()
            }
            adapter = options.pop("service", None)
            if adapter == "Disk":
                root = Path(options.pop("root"))
                self.services[name] = DiskService(self.root / root, **options)
            elif adapter == "S3":
                self.services[name] = S3Service(**options)
            else:
                raise StorageError(f"Unknown storage adapter {adapter!r}")
            self.services[name].name = name
        return self.services[name]

    @staticmethod
    def _resolve(value):
        if isinstance(value, dict):
            if set(value) == {"env"}:
                name = value["env"]
                if name not in os.environ:
                    raise StorageError(f"Missing storage environment variable {name}")
                return os.environ[name]
            if set(value) == {"credential"}:
                result = current_app.credentials.to_dict()
                for key in value["credential"].split("."):
                    if not isinstance(result, dict) or key not in result:
                        raise StorageError(
                            f"Missing storage credential {value['credential']}"
                        )
                    result = result[key]
                return result
            return {
                key: AttachmentsExtension._resolve(item) for key, item in value.items()
            }
        return value

    def _register_routes(self, app):
        blueprint = Blueprint("flaskteroids_attachments", __name__)

        def find_blob(signed_id):
            try:
                blob = Blob.find_signed_or_raise(signed_id)
            except (BadSignature, RecordNotFoundException):
                abort(404)
            authorize = current_app.config.attachments.authorize
            if authorize is not None and not authorize(blob):
                abort(404)
            return blob

        def disposition():
            value = request.args.get("disposition", "inline")
            if value not in {"inline", "attachment"}:
                abort(400)
            return value

        @blueprint.get(
            "/flaskteroids/attachments/blobs/redirect/<signed_id>/<filename>",
            endpoint="redirect",
        )
        def redirect_blob(signed_id, filename):
            blob = find_blob(signed_id)
            duration = current_app.config.attachments.service_urls_expire_in
            response = redirect(
                blob.url(expires_in=duration, disposition=disposition())
            )
            response.headers["Cache-Control"] = f"private, max-age={duration}"
            if current_app.config.attachments.authorize is not None:
                response.headers["Cache-Control"] = "private, no-store"
            return response

        @blueprint.get(
            "/flaskteroids/attachments/blobs/proxy/<signed_id>/<filename>",
            endpoint="proxy",
        )
        def proxy_blob(signed_id, filename):
            blob = find_blob(signed_id)
            try:
                options = blob.serving_options(disposition())
                service = blob.service
                if isinstance(service, DiskService):
                    response = send_file(
                        service.path_for(blob.key),
                        mimetype=options["content_type"],
                        as_attachment=options["disposition"] == "attachment",
                        download_name=blob.filename,
                        conditional=True,
                        etag=blob.key,
                        max_age=3153600000,
                    )
                else:
                    response = current_app.response_class(
                        mimetype=options["content_type"], direct_passthrough=True
                    )
                    response.headers["Content-Disposition"] = content_disposition(
                        blob.filename, options["disposition"]
                    )
                    response.content_length = blob.byte_size
                    response.set_etag(blob.key)
                    response.make_conditional(
                        request.environ,
                        accept_ranges=True,
                        complete_length=blob.byte_size,
                    )
                    if request.method != "HEAD" and response.status_code in {200, 206}:
                        byte_range = (
                            {
                                "start": response.content_range.start,
                                "end": response.content_range.stop - 1,
                            }
                            if response.status_code == 206
                            else {}
                        )
                        response.response = wrap_file(
                            request.environ,
                            service.open(blob.key, **byte_range),
                            buffer_size=64 * 1024,
                        )
            except FileNotFoundError:
                abort(404)
            response.headers["Accept-Ranges"] = "bytes"
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["Cache-Control"] = "public, max-age=3153600000, immutable"
            if current_app.config.attachments.authorize is not None:
                response.headers["Cache-Control"] = "private, no-store"
            return response

        @blueprint.get(
            "/flaskteroids/attachments/disk/<encoded_key>/<filename>", endpoint="disk"
        )
        def disk_file(encoded_key, filename):
            try:
                payload = verified_token("blob_key", encoded_key)
                if any(
                    not isinstance(payload.get(key), str)
                    for key in (
                        "key",
                        "service_name",
                        "filename",
                        "content_type",
                        "disposition",
                    )
                ) or payload["disposition"] not in {"inline", "attachment"}:
                    abort(404)
                service = self.service(payload["service_name"])
                if not isinstance(service, DiskService):
                    abort(404)
                response = send_file(
                    service.path_for(payload["key"]),
                    mimetype=payload["content_type"],
                    as_attachment=payload["disposition"] == "attachment",
                    download_name=payload["filename"],
                    conditional=True,
                    max_age=0,
                )
            except (BadSignature, StorageError, FileNotFoundError):
                abort(404)
            response.headers["X-Content-Type-Options"] = "nosniff"
            return response

        app.register_blueprint(blueprint)
