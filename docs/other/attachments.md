# Attachments

Use attachments to give a model one file, such as an avatar, or a collection of
files, such as documents. File bytes live in a configured storage service;
the database keeps attachment records and metadata.

After reading this guide, you will know how to:

- Add single or multiple file uploads to a model.
- Accept uploads in a form and display download links.
- Choose storage, protect private files, and remove uploads.

## Set up

To generate a resource with file uploads, run these commands inside your application:

```sh
bin/flask generate scaffold User name:string avatar:attachment documents:attachments
bin/flask attachments:install
bin/flask db:migrate
```

Model, resource, and scaffold generators accept `name:attachment` for one file and
`name:attachments` for multiple files. Here, `avatar` and `documents` are attachment
names, not database columns. The scaffold generates the model declarations, upload
inputs, controller parameters, and file links.

`bin/flask attachments:install` creates an attachment migration and adds
`config/storage.yml` if missing. `bin/flask db:migrate` applies the migrations.

## Add attachments to a model

To add attachments to an existing model without a generator, declare them with
`has_one_attached` or `has_many_attached`. Run `bin/flask attachments:install` and
`bin/flask db:migrate` if attachments have not been set up yet.

```python
from app.models.application_model import ApplicationModel
from flaskteroids.model import has_one_attached, has_many_attached


class User(ApplicationModel):
    has_one_attached("avatar")
    has_many_attached("documents")
```

Pass an uploaded file to `attach`, or include it in `create` or `update`:

```python
user.avatar.attach(upload)
user.update(avatar=another_upload)
user.documents.attach(first_upload, second_upload)
```

For multiple files, `attach` **adds** to the collection;
`user.update(documents=[upload])` **replaces** it. For a new record or one with
unsaved changes, call `save()` after attaching.

You can also attach an open file:

```python
with open("avatar.png", "rb") as stream:
    user.avatar.attach(io=stream, filename="avatar.png")
```

Use `user.avatar.attached()` to check for a file and `user.avatar.filename` to
read its name.

### When files become available

Uploads become available **after commit**:

- A standalone save commits before returning.
- Attaching to a saved record with no pending changes also commits before returning.
- Inside `Model.transaction()`, uploads wait for the block to commit.
- In model callbacks, read new uploads in `after_commit`, not `after_save`.

Standalone blob creation and explicit attachment removal also commit their own
transaction unless they join an explicit block.

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
attributes = self.params.expect(user=["avatar", ("documents", [])])
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

Application links are permanent by default. `user.avatar.url()` instead returns
a direct storage URL that normally expires after five minutes.

**Anyone holding a signed link can download the file by default.** A signature
prevents tampering; it does not check who is using the link. Share links and signed
IDs only with authorized users, or add the permission check below.

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

The callback receives a blob (the stored file record). It can inspect
`blob.attachments` to check ownership and the browser session to identify the user.
**Download routes do not run controller authentication callbacks.** Denied
downloads return 404.

Use `blob_path` or `blob_url` for private files. Direct storage URLs bypass the
permission check, so avoid `user.avatar.url()` and public storage for those files.

## Storage

Edit `config/storage.yml` to define your services:

```yaml
local:
  service: Disk
  root: storage

test:
  service: Disk
  root: tmp/storage

archive:
  service: Disk
  root: storage/archive
```

Relative disk paths start at the application root. Keep the storage directory
persistent when deploying containers. Generated Docker applications use writable
`/app/storage` for SQLite and local uploads; mount persistent storage there.
Host bind mounts must be writable by the image user. `bin/setup` and default web
startup create only conventional storage, not arbitrary configured directories.

Disk storage is built in. Additional providers are installed separately and
register through the `flaskteroids.storage` entry point group. No application
import or initializer is needed. Installation makes a provider available; it
does not change the selected service. Follow the provider package's documentation
for its configuration and credentials.

For example, `flaskteroids-storage-s3` provides S3-compatible storage; its setup
and provider-specific options are documented in that package.

Select a service in your environment configuration:

```python
config.attachments.service = "archive"
```

Generated applications use `local` in development and `test` in tests. Production
uses `FLASKTEROIDS_ATTACHMENTS_SERVICE`, defaulting to `local`. A declaration can override the
default with `service="archive"`. Changing services does not move existing files.

### Custom storage providers

Additional storage services are supplied by provider packages. Installing a
provider makes it available; select it in `config/storage.yml` and follow the
package's setup instructions. A missing or invalid selected provider fails
explicitly rather than falling back to local storage.

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

A blob is a stored file record; it can exist without an attachment, for example
after someone abandons an upload form. Cleanup is not scheduled automatically.

Schedule a job that calls `Blob.purge_unattached()` to enqueue deletion of
unattached blobs older than two days. Use a positive `older_than=timedelta(...)`
to choose another grace period. This covers all unattached blobs, including
rich-text uploads. Purge jobs recheck attachments before deleting files.

## Tests

Place files in `test/fixtures/files` and attach them in your tests:

```python
from test.test_helper import fixture_file_upload

user.avatar.attach(fixture_file_upload("avatar.png"))
```

Tests use temporary local storage, even when the application uses a remote
provider. Browser tests can use
`self.attach_file("Avatar", "test/fixtures/files/avatar.png")`.
See [Testing](../testing.md) for test setup.
