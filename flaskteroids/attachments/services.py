import base64
import hashlib
import hmac
import io
import re
import shutil
from pathlib import Path
from urllib.parse import quote, urlsplit, urlunsplit

from flask import url_for

from flaskteroids.attachments.filenames import content_disposition
from flaskteroids.attachments.signatures import signed_token


class StorageError(RuntimeError):
    pass


class IntegrityError(StorageError):
    pass


class UploadTooLarge(StorageError):
    pass


def verify_checksum(data, checksum):
    stream = io.BytesIO(data) if isinstance(data, bytes) else data
    digest = hashlib.md5(usedforsecurity=False)
    stream.seek(0)
    while chunk := stream.read(64 * 1024):
        digest.update(chunk)
    stream.seek(0)
    actual = base64.b64encode(digest.digest()).decode()
    if not hmac.compare_digest(actual, checksum):
        raise IntegrityError("The uploaded file does not match its checksum")


def validate_key(key):
    if not isinstance(key, str) or not re.fullmatch(r"[a-z0-9]{28,64}", key):
        raise StorageError("Invalid storage key")


class DiskService:
    def __init__(self, root, *, public=False):
        self.root = Path(root).resolve()
        self.public = public
        self.name = None

    def path_for(self, key):
        validate_key(key)
        path = self.root / key[:2] / key[2:4] / key
        if not path.resolve().is_relative_to(self.root):
            raise StorageError("Storage path escapes its root")
        return path

    def upload(
        self,
        key,
        data,
        *,
        checksum=None,
        content_type=None,
        filename=None,
        disposition=None,
    ):
        stream = io.BytesIO(data) if isinstance(data, bytes) else data
        path = self.path_for(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("wb") as destination:
            shutil.copyfileobj(stream, destination)
        if checksum is not None:
            try:
                with path.open("rb") as stored:
                    verify_checksum(stored, checksum)
            except IntegrityError:
                self.delete(key)
                raise

    def download(self, key, callback=None):
        with self.path_for(key).open("rb") as stream:
            if callback is None:
                return stream.read()
            while chunk := stream.read(64 * 1024):
                callback(chunk)

    def delete(self, key):
        self.path_for(key).unlink(missing_ok=True)

    def exist(self, key):
        return self.path_for(key).is_file()

    def url(self, key, *, expires_in, filename, content_type, disposition):
        validate_key(key)
        token = signed_token(
            "blob_key",
            {
                "key": key,
                "service_name": self.name,
                "filename": filename,
                "content_type": content_type,
                "disposition": disposition,
            },
            None if self.public else expires_in,
        )
        return url_for(
            "flaskteroids_attachments.disk",
            encoded_key=token,
            filename=filename,
            _external=True,
        )


class S3Service:
    def __init__(
        self,
        *,
        bucket,
        client=None,
        region=None,
        access_key_id=None,
        secret_access_key=None,
        endpoint=None,
        force_path_style=False,
        public=False,
    ):
        if client is None:
            try:
                import boto3
            except ImportError as error:
                raise StorageError(
                    'S3 storage requires the optional dependency: pip install "flaskteroids[s3]"'
                ) from error
            from botocore.config import Config

            options = {
                "region_name": region,
                "aws_access_key_id": access_key_id,
                "aws_secret_access_key": secret_access_key,
                "endpoint_url": endpoint,
            }
            client = boto3.client(
                "s3",
                config=Config(
                    s3={"addressing_style": "path" if force_path_style else "auto"}
                ),
                **{key: value for key, value in options.items() if value is not None},
            )
        self.bucket = bucket
        self.client = client
        self.public = public
        self.force_path_style = force_path_style
        self.name = None

    def upload(
        self,
        key,
        data,
        *,
        checksum=None,
        content_type=None,
        filename=None,
        disposition=None,
    ):
        validate_key(key)
        if checksum is not None:
            verify_checksum(data, checksum)
        options = {"Bucket": self.bucket, "Key": key, "Body": data}
        if checksum is not None:
            options["ContentMD5"] = checksum
        if content_type is not None:
            options["ContentType"] = content_type
        if filename is not None and disposition is not None:
            options["ContentDisposition"] = content_disposition(filename, disposition)
        if self.public:
            options["ACL"] = "public-read"
        self.client.put_object(**options)

    def open(self, key, *, start=None, end=None):
        validate_key(key)
        options = {"Bucket": self.bucket, "Key": key}
        if start is not None:
            options["Range"] = f"bytes={start}-{end if end is not None else ''}"
        try:
            response = self.client.get_object(**options)
        except Exception as error:
            code = getattr(error, "response", {}).get("Error", {}).get("Code")
            if code in {"404", "NoSuchKey", "NotFound"}:
                raise FileNotFoundError(key) from error
            raise
        return response["Body"]

    def download(self, key, callback=None):
        with self.open(key) as stream:
            if callback is None:
                return stream.read()
            while chunk := stream.read(64 * 1024):
                callback(chunk)

    def delete(self, key):
        validate_key(key)
        self.client.delete_object(Bucket=self.bucket, Key=key)

    def exist(self, key):
        validate_key(key)
        try:
            self.client.head_object(Bucket=self.bucket, Key=key)
        except Exception as error:
            code = getattr(error, "response", {}).get("Error", {}).get("Code")
            if code in {"404", "NoSuchKey", "NotFound"}:
                return False
            raise
        return True

    def url(self, key, *, expires_in, filename, content_type, disposition):
        validate_key(key)
        if self.public:
            parts = urlsplit(self.client.meta.endpoint_url)
            if self.force_path_style:
                path = f"{parts.path.rstrip('/')}/{quote(self.bucket)}/{key}"
                return urlunsplit((parts.scheme, parts.netloc, path, "", ""))
            return urlunsplit(
                (parts.scheme, f"{self.bucket}.{parts.netloc}", f"/{key}", "", "")
            )
        return self.client.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": self.bucket,
                "Key": key,
                "ResponseContentType": content_type,
                "ResponseContentDisposition": content_disposition(
                    filename, disposition
                ),
            },
            ExpiresIn=expires_in,
        )
