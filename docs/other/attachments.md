# Attachments

Attach uploaded files to models using disk or S3-compatible storage.

## Set up

To generate a resource with file uploads, run these commands inside your application:

```sh
flask generate scaffold User name:string avatar:attachment documents:attachments
flask attachments:install
flask db:migrate
```

Model, resource, and scaffold generators accept `name:attachment` for one file and
`name:attachments` for multiple files. Here, `avatar` and `documents` are attachment
names, not database columns. The scaffold generates the model declarations, upload
inputs, controller parameters, and file links.

`flask attachments:install` creates an attachment migration and adds
`config/storage.yml` if it is missing. `flask db:migrate` applies the model and
attachment migrations.

## Add attachments to a model

To add attachments to an existing model without a generator, declare them with
`has_one_attached` or `has_many_attached`. Run `flask attachments:install` and
`flask db:migrate` if attachments have not been set up yet.

```python
from app.models.application_model import ApplicationModel
from flaskteroids.model import has_one_attached, has_many_attached


class User(ApplicationModel):
    has_one_attached('avatar')
    has_many_attached('documents')
```

Pass an uploaded file to `attach`, or include it in `create` or `update`:

```python
user.avatar.attach(upload)
user.update(avatar=another_upload)
user.documents.attach(first_upload, second_upload)
```

`attach` appends to a collection. `user.update(documents=[upload])` replaces it.
For new records or records with unsaved changes, call `save()` after attaching.

You can also attach an open file:

```python
with open("avatar.png", "rb") as stream:
    user.avatar.attach(io=stream, filename="avatar.png")
```

Use `user.avatar.attached()` to check for a file and `user.avatar.filename` to
read its name. Files become available after commit: standalone saves and attaches
to clean persisted records commit before returning; operations in an explicit
`Model.transaction()` wait for that block to commit. In model callbacks, read new
uploads in `after_commit`, not `after_save`. Standalone blob creation and explicit
attachment removals also own a transaction unless joining an explicit block.

## Upload forms

```html
{% call(form) form_with(model=user) %}
  {{ form.label("avatar") }}
  {{ form.file_field("avatar") }}

  {{ form.label("documents") }}
  {% for document in user.documents %}
    {{ form.hidden_field("documents", multiple=True, value=document.signed_id()) }}
  {% endfor %}
  {{ form.file_field("documents", multiple=True) }}
  {{ form.submit() }}
{% endcall %}
```

`form_with` handles multipart encoding. The hidden fields keep existing documents;
without them, submitting the multiple file field replaces the collection,
including clearing it when no files are selected. An empty single file input keeps
the existing attachment.

Permit uploads in your controller:

```python
attributes = params.expect(user=["avatar", ("documents", [])])
user.update(**attributes)
```

`expect` requires the outer `user` dictionary, not every permitted upload field.
Keep a fixed allowlist: omitted fields are excluded from `attributes`, so a partial
update leaves their attachments unchanged. To clear a collection, submit an empty
list explicitly rather than omitting the field.

## Validation and limits

Replace the existing avatar declaration inside `User` with one that includes
size and content-type checks. Keep its other declarations and methods:

```python
from app.models.application_model import ApplicationModel
from flaskteroids.model import has_one_attached


class User(ApplicationModel):
    has_one_attached(
        "avatar",
        max_size=2 * 1024 * 1024,
        content_types=["image/png", "image/jpeg"],
    )

    # Keep other declarations and methods here.
```

Failed checks add messages to the model's `errors` and prevent saving.
Content-type checks do not replace file scanning.

There is no per-file size limit by default. Set limits in your configuration:

```python
config.attachments.max_upload_size = 20 * 1024 * 1024  # Per file
config["MAX_CONTENT_LENGTH"] = 25 * 1024 * 1024        # Entire request
```

Uploads over these limits return HTTP 413.

## Storage

Edit `config/storage.yml` to define your services:

```yaml
local:
  service: Disk
  root: storage

test:
  service: Disk
  root: tmp/storage

amazon:
  service: S3
  bucket: {env: S3_BUCKET}
  region: {env: AWS_REGION}
```

Relative disk paths start at the application root. Keep the storage directory
persistent when deploying containers. Generated Docker applications use writable
`/app/storage` for SQLite and local uploads; mount persistent storage there.
Host bind mounts must be writable by the image user. `bin/setup` and default web
startup create only conventional storage, not arbitrary configured directories.

For S3, install the optional dependency:

```sh
uv add "flaskteroids[s3]"
```

S3 uses your AWS credentials or IAM role. It also accepts `endpoint` and
`force_path_style` for compatible providers.

Select a service in your environment configuration:

```python
config.attachments.service = "amazon"
```

Generated applications use `local` in development and `test` in tests. Production
uses `FLASKTEROIDS_ATTACHMENTS_SERVICE`, defaulting to `local`. A declaration can override the
default with `service="amazon"`. Changing services does not move existing files.

## Download links

Use `blob_path` in templates:

```html
{% if user.avatar.attached() %}
  <img src="{{ blob_path(user.avatar) }}" alt="Avatar">
{% endif %}
```

`blob_path` returns a relative link; `blob_url` returns an absolute URL. Both are
also available from `flaskteroids.attachments` in Python. Use
`blob_path(user.avatar, disposition="attachment")` to force a download, or pass
`expires_in=3600` for a link that expires after an hour.

Application links are permanent by default. `user.avatar.url()` returns a direct
storage URL that normally expires after five minutes.

Anyone with a signed link can download the file by default. Only expose signed
links and IDs to users allowed to access the file.

## Private files

Define `can_download(blob)` in `app/helpers/permissions.py` to check permissions
and return `True` or `False`. Configure it in an initializer:

```python
# config/initializers/attachments.py
from flask import current_app
from app.helpers.permissions import can_download

current_app.config.attachments.authorize = can_download
current_app.config.attachments.resolve_model_to_route = "proxy"
```

The callback can inspect `blob.attachments` to check ownership. Check the browser
session in the callback; these routes do not run controller authentication
callbacks. Denied downloads return 404.

Use `blob_path` or `blob_url` for private files. Direct storage URLs bypass the
permission check, so avoid `user.avatar.url()` and public storage for those files.

## Remove files

```python
user.avatar.detach()       # Keep the file, remove the attachment
user.avatar.purge_later()  # Delete the file in a background job
user.avatar.purge()        # Delete the file now
```

Replacing attachments or deleting their record schedules file deletion by default.
Run your Celery worker to process these jobs. Shared files are not purged while
another attachment uses them.

Prefer `purge_later` in transactions and callbacks. Rolling back after `purge`
does not restore the deleted file.

## Unattached uploads

Schedule a job calling `Blob.purge_unattached()` to enqueue purging of blobs
that are unattached and older than two days. Use a positive
`older_than=timedelta(...)` to change the grace period. This includes abandoned
rich-text uploads and all other unattached blobs. Jobs recheck attachments
before deleting files. Cleanup is not scheduled automatically.

## Tests

Place files in `test/fixtures/files` and attach them in your tests:

```python
from test.test_helper import fixture_file_upload

user.avatar.attach(fixture_file_upload("avatar.png"))
```

Tests use temporary local storage, even when the application uses S3. Browser
tests can use `self.attach_file("Avatar", "test/fixtures/files/avatar.png")`.
See [Testing](../testing.md) for test setup.
