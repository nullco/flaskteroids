# Rich text

Declare rich-text attributes, edit them with Trix, and render formatted text,
images, and file attachments without implementing editor or storage plumbing.

## Set up

```sh
bin/flask generate scaffold Post title:string content:rich_text
bin/flask rich_text:install
bin/flask db:migrate
```

Restart the server, then visit `/posts`. The scaffold includes the declaration,
editor, permitted parameters, display templates, and fixtures.

The installer generates shared `rich_texts` storage and, if not already installed,
the attachment tables and `config/storage.yml`. It copies local Trix assets and
adds `{{ rich_text_assets() }}` to `app/views/layouts/application.html`.
No Node, npm, or editor CDN is required. Custom layouts should include that helper
once in their `<head>`.

Repeated installation preserves existing files and avoids duplicate migrations.
After upgrading Flaskteroids, **review application-owned asset customizations**,
then refresh the integration with:

```sh
bin/flask rich_text:install --force
bin/flask db:migrate
```

`--force` replaces installed editor assets, including custom CSS/JavaScript, not
the layout or storage configuration. This is required when upgrading from the
text-only integration. Assets use normal production fingerprinting through
`bin/flask assets:precompile`; generated Docker builds already run it.

## Model declarations

```python
from app.models.application_model import ApplicationModel
from flaskteroids.model import has_rich_text, validates


class Post(ApplicationModel):
    has_rich_text("content")
    has_rich_text("summary", store_if_blank=False)
    validates("title", presence=True)
    validates("content", presence=True)
```

There is no `content` column on `posts`. Existing text columns need an explicit
data migration and column removal before switching to a rich-text declaration.
Owners require a single integer `id` primary key. Renaming a model also requires
migrating its `rich_texts.record_type` values.

### Declaration options

- `store_if_blank=True` (default): explicit blank assignment stores an empty body.
  With `False`, assigning `None` or blank HTML through the owner skips a missing
  rich-text row or marks an existing row for destruction on the next successful
  owner save. Omitted attributes are unchanged.
- `strict_loading=True`: accessing an unloaded rich-text association raises
  `StrictLoadingViolationError`, rather than silently querying. Use an eager
  scope. New records and assigned bodies remain usable. The default inherits
  `strict_loading_by_default` from the application model, normally `False`.
  This default currently applies to rich-text declarations, not general ORM
  association strict loading.
- `encrypted=True`: transparently encrypts the stored body using a dedicated key;
  see [Encryption](#encryption).

Presence validation checks visible text and verified attachments. Formatting-only
markup such as `<div><br></div>` is blank.

## Assignment and rich-text records

```python
post = Post.new(title="Hello", content="<div>Hello <strong>world</strong></div>")
post.save()
post.content = "<div>Revised</div>"
post.save()
```

`post.content` returns a stable `RichText` record; its `body` is an immutable
`Content` value. Both assignment styles autosave with the owner:

```python
post.content.body = "<em>Another revision</em>"
post.save()

assert post.rich_text_content is post.content
assert post.content.record is post
```

Assignment does not publish changes to unrelated saves. Failed validation retains
the body and uploaded attachments for correction and form redisplay. Saves join
the owner's transaction; destroying the owner destroys its rich-text rows and
schedules dependent attachment cleanup.

Reading an unset attribute builds an empty rich-text record in memory. Reading
alone does not write to the database. `post.reload()` discards submitted body
changes and reloads persisted content.

### Independent persistence

```python
post.content.update(body="<div>Saved independently</div>")
post.content.body = "<div>A second revision</div>"
post.content.save()
post.content.reload()

from flaskteroids.rich_text import RichText

content = RichText.find(post.content.id)
content.record
content.body
content.errors
content.is_new_record()
content.is_persisted()
```

Independent saves of persisted owners **do not validate or save their other
pending attributes**; they touch the owner's `updated_at`. They still join an
explicit framework transaction. Saving a rich-text record whose owner is new
saves and validates that owner first. `content.destroy()` removes the rich-text
record and its embeds without destroying the owner.

## Forms and parameters

```jinja
{% call(form) form_with(model=post) %}
  {{ form.label("title") }}
  {{ form.text_field("title") }}
  {{ form.label("content") }}
  {{ form.rich_text_area("content", placeholder="Write something…") }}
  {{ form.submit("Save") }}
{% endcall %}
```

Trix uses an escaped hidden input, model prefixes, accessible labels, normal
CSRF protection, and validation redisplay. Permit the body as a scalar:

```python
def _post_params(self):
    return self.params.expect(post=["title", "content"])
```

Uploads use the model-backed form's signed, session-bound upload capability and
CSRF token. The editor supports file selection, drag-and-drop, and pasted image
files. Submission waits for outstanding uploads, including with Turbo. Failed
uploads display an alert and block submission until removed or retried.
Standalone editors without a model-backed upload capability are text-only.

## Rendering and attachments

```jinja
{{ post.content }}
```

This renders sanitized HTML inside `<div class="trix-content">`. Do not add
`|safe` or wrap user input in `Markup`. Server sanitization remains the security
boundary, regardless of the editor or request source.

Embedded attachments use verified, purpose-specific blob signatures. The server
ignores client-supplied file URLs, filenames, types, sizes, and executable HTML;
it resolves metadata from storage. Unverified or missing attachments are removed.
Adjacent raster image previews render as a gallery. Other files render as
download links. Active formats such as SVG and HTML use the existing attachment
system's forced-download policy.

Programmatic attachment insertion uses the same storage API:

```python
from flaskteroids.attachments import Blob

with open("photo.png", "rb") as stream:
    photo = Blob.create_and_upload(io=stream, filename="photo.png")

post.content.body = post.content.body.append_attachables([photo])
post.save()
post.content.embeds.blobs
```

`embeds` exposes the usual attachment collection operations. Normally, remove
an embed by editing the body and saving it. Removed embeds and destroyed owners
schedule purging **after commit**. Shared blobs remain until their final
attachment is removed. Run the job worker to process purge jobs.

Body APIs include:

```python
post.content.to_plain_text()       # Ordinary text, including attachment captions/names
post.content.to_trix_html()        # Sanitized editor HTML
post.content.body.to_html()        # Canonical body with signed attachment references
post.content.body.attachables      # Verified Blob objects
post.content.blank()
post.content.present()
```

These string-returning methods are not marked HTML-safe. Use the attribute itself
for HTML display. Model JSON responses do not automatically include associations;
select body fields explicitly in your model's `__json__()`.

### Upload permissions, limits, and private files

The upload capability is issued when an authorized controller renders the form.
Upload routes do not run application controller callbacks. For permissions that
must be checked again at upload time, configure a callback in an initializer:

```python
from flask import current_app
from app.helpers.permissions import can_upload_rich_text

# Callable(model_class, record_id_or_none, attribute_name) -> bool
current_app.config.rich_text.authorize_upload = can_upload_rich_text
```

New-owner forms pass `None` as the record ID. Form capabilities expire after an
hour; configure `config.rich_text.upload_token_expires_in` if needed.

Uploads honor `config.attachments.max_upload_size` and Flask's
`MAX_CONTENT_LENGTH`. Set appropriate limits for your deployment; neither
attachment encryption nor content-type detection replaces malware scanning.

Downloads and image previews use the existing attachment routes and
`config.attachments.authorize` callback. For private files, use proxy routing.
An embed's attachment has `record_type == "RichText"`; its owner is accessible
through `RichText.find(attachment.record_id).record`. A callback that authorizes
only already-attached blobs will also deny previews of new draft uploads.
Account for draft-upload access explicitly in your permission policy if needed;
upload authorization does not bypass download authorization.

Signed attachment references are bearer capabilities, as with ordinary signed
blob IDs. Only expose them to users allowed to reuse those files. See
[Attachments](attachments.md) for storage services, private downloads, and limits.

### Abandoned uploads

Uploads from abandoned forms remain unattached so failed validation does not
destroy files awaiting resubmission. Schedule a job that calls:

```python
Blob.purge_unattached()
```

This queues cleanup of **all storage blobs** that are unattached and older than
two days, not only rich-text uploads. Set a positive `older_than=timedelta(...)`
for another grace period. Purge jobs recheck attachments before deleting, so a
file attached after the sweep is retained. Cleanup is not scheduled automatically.

## Eager loading

```python
Post.with_rich_text_content()             # Body record
Post.with_rich_text_content_and_embeds()  # Body, attachment metadata, and blobs
Post.where(title="Hello").with_rich_text_content_and_embeds()
Post.with_all_rich_text()                # All declared rich text and embeds
```

Scopes remain chainable model queries. Generated index actions preload all rich
text and embeds. Body-only loading is also available through
`Post.includes("rich_text_content")`. With strict loading, rendering attachments
requires an embed-loading scope. Rich-text attributes are not scalar columns and
cannot be searched using `Post.where(content=...)`.

## Encryption

Rich text uses the same [attribute encryption](../models/encryption.md) service
and dedicated keys as ordinary model attributes:

```sh
bin/flask db:encryption:init
bin/flask credentials:edit
```

Store the generated `active_record_encryption` YAML in encrypted credentials.
The primary key encrypts rich-text bodies; neither the credentials master key nor
the Flask signing secret is reused.

```python
class Post(ApplicationModel):
    has_rich_text("content", encrypted=True)
```

Bodies use randomized, authenticated encryption. Missing/wrong keys, modified
ciphertext, and unexpected plaintext raise `EncryptionError` by default. Editing
and rendering still expose plaintext to the authorized application/browser.
Rich text does not accept per-field deterministic encryption options.

For randomized-key rotation, configure
`config.active_record.encryption.primary_key = [previous_key, current_key]`.
The last key encrypts; all keys may decrypt. Re-encrypt before retiring old keys:

```python
for post in Post.with_rich_text_content():
    post.content.encrypt()
```

The same explicit method migrates plaintext bodies after enabling encryption,
without requiring permissive plaintext reads. Perform migrations before serving
normal traffic; back up data and retain keys needed for old backups.

Encryption covers the body, not uploaded file bytes, attachment metadata, or
rendered responses. Use storage-provider encryption and download authorization
for files. Envelopes are Flaskteroids-specific, not Rails ciphertext-compatible.

## Tests

Scaffold fixtures accept HTML inline, including encrypted rich-text attributes:

```yaml
one:
  title: Hello
  content: "<div>Hello <strong>world</strong></div>"
```

Configure test encryption keys when the declared field is encrypted. Fixtures
use the normal rich-text persistence layer without running owner save callbacks.

```python
self.fill_in_rich_text_area("Content", with_="<div>Hello <strong>world</strong></div>")
self.click_on("Save")
self.assert_selector(".trix-content strong", text="world")
```

The helper fills HTML through Trix's public editor API. Normal keyboard and file
interaction remain available through the Playwright page.

## Rails compatibility boundaries

Declarations, editable rich-text records, owner autosave, independent persistence,
Trix forms, signed embeds, eager scopes, and the three declaration options follow
Action Text's application workflow. This is not a drop-in Action Text database or
serialization implementation.

Arbitrary record embeds, custom attachment-rendering partials, image resizing,
video/PDF preview generation, rich-text search, and the full Active Record API on
`RichText` are not implemented. Sanitized HTML and plain-text formatting are not
guaranteed byte-for-byte identical to Rails.
