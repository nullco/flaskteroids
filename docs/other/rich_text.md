# Rich text

Add formatted text, images, and file attachments with a model declaration and a
form field. Flaskteroids provides the Trix editor, storage integration, and safe
HTML rendering.

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
Production assets are built with `bin/flask assets:precompile`; generated Docker
builds already do this. See [upgrading the editor](#upgrade-the-editor) when
refreshing an existing installation.

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
  With `False`, assigning `None` or blank HTML avoids creating an empty row. If a
  row already exists, it is removed on the model's next successful save. Omitting
  the attribute leaves it unchanged.
- `strict_loading=True`: require content to be preloaded rather than issuing an
  extra query when accessed. Otherwise, `StrictLoadingViolationError` is raised.
  Use an [eager-loading scope](#eager-loading). New records and assigned bodies
  remain usable. The default comes from the model's `strict_loading_by_default`,
  normally `False`; it currently applies to rich text, not all ORM associations.
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

`post.content` is a `RichText` record, not a plain string. Its `body` is an
immutable `Content` value: replace it rather than editing it in place. You can
assign the attribute directly, as above, or assign its body. Both are saved when
you save the owning `Post`:

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
from flaskteroids.rich_text import RichText

post.content.update(body="<div>Saved independently</div>")
post.content.body = "<div>A second revision</div>"
post.content.save()
post.content.reload()

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

Model-backed forms include a signed upload token tied to the browser session,
plus a CSRF token. The editor supports file selection, drag-and-drop, and pasted
images. Submission waits for uploads to finish, including when using Turbo. If an
upload fails, an alert appears and submission is blocked until it is removed or
retried. Standalone editors without the model-backed upload token are text-only.

## Rendering and attachments

```jinja
{{ post.content }}
```

This renders sanitized HTML inside `<div class="trix-content">`. Do not add
`|safe` or wrap user input in `Markup`. The server sanitizes content
regardless of whether it came from Trix or another request source.

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

The upload token is issued when your controller renders the form, so authorize
access to that form. **Upload routes do not run application controller callbacks.**
If permissions must be checked again at upload time, configure a callback in an
initializer:

```python
from flask import current_app
from app.helpers.permissions import can_upload_rich_text

# Callable(model_class, record_id_or_none, attribute_name) -> bool
current_app.config.rich_text.authorize_upload = can_upload_rich_text
```

Forms for new records pass `None` as the record ID. Upload tokens expire after an
hour; change `config.rich_text.upload_token_expires_in` if needed.

Uploads honor `config.attachments.max_upload_size` and Flask's
`MAX_CONTENT_LENGTH`. Set limits for your deployment. Rich-text encryption does
not encrypt uploaded file bytes, and content-type checks do not replace malware
scanning.

Downloads and image previews use the existing attachment routes and
`config.attachments.authorize` callback. For private files, use proxy routing.
An embed's attachment has `record_type == "RichText"`; its owner is accessible
through `RichText.find(attachment.record_id).record`. A callback that authorizes
only already-attached blobs will also deny previews of new draft uploads.
Account for draft-upload access explicitly in your permission policy if needed;
upload authorization does not bypass download authorization.

Anyone holding a signed attachment reference may reuse it, just as with an
ordinary signed blob ID. Share these references only with users allowed to reuse
the files. See
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

Preloading avoids extra queries when displaying several records. These methods
return chainable model queries. Generated index actions already preload rich text
and embedded attachments. For the body alone, you can also use
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

Store the generated `encryption` YAML in encrypted credentials.
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
`config.encryption.primary_key = [previous_key, current_key]`.
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
for files. Ciphertext uses Flaskteroids-specific envelopes.

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
self.fill_in_rich_text_area("Content", value="<div>Hello <strong>world</strong></div>")
self.click_on("Save")
self.assert_selector(".trix-content strong", text="world")
```

The helper fills HTML through Trix's public editor API. Normal keyboard and file
interaction remain available through the Playwright page.

## Upgrade the editor

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

## Limitations

Arbitrary record embeds, custom attachment-rendering partials, image resizing,
video/PDF preview generation, and rich-text search are not implemented.
`RichText` provides the record operations documented here, not the full
`Model` API.
