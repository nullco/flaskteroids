# Rich text

Declare rich-text attributes, edit them with Trix, and render formatted content
without adding HTML-handling code to your application.

## Generate a resource

Inside your application:

```sh
bin/flask generate scaffold Post title:string content:rich_text
bin/flask rich_text:install
bin/flask db:migrate
```

Restart the server, then visit `/posts`. The scaffold includes a model declaration,
a Trix editor, permitted controller parameters, formatted display, and fixtures.

The installer creates a migration for the shared `rich_texts` table, copies
local Trix JavaScript/CSS into `app/assets/rich_text`, and adds
`{{ rich_text_assets() }}` to `app/views/layouts/application.html`. It does not
apply migrations or require Node, npm, or an editor CDN. Repeated runs preserve
existing assets/layout content and avoid duplicate migrations.

For a custom layout, include the helper once inside its `<head>`:

```jinja
{{ rich_text_assets() }}
```

Assets participate in normal production fingerprinting through
`bin/flask assets:precompile`; generated Docker builds already run that command.
Installed assets are application-owned. A framework upgrade does not overwrite
them: review upstream changes and deliberately replace the bundled Trix assets
to adopt editor/security updates. Preserve their license files.

## Add rich text to an existing model

Install shared storage once per application, then declare as many named
attributes as you need:

```python
from app.models.application_model import ApplicationModel
from flaskteroids.model import has_rich_text, validates


class Post(ApplicationModel):
    has_rich_text("content")
    has_rich_text("summary")
    validates("title", presence=True)
    validates("content", presence=True)
```

There is no `content` column on `posts`. Do not also generate a text column with
the same name. Existing text columns need an explicit data migration and column
removal before switching the declaration.

Owners currently require a single integer `id` primary key. Shared storage
identifies them by model class name and ID. When renaming a model, migrate its
`rich_texts.record_type` values too.

## Assign and save

```python
post = Post.new(title="Hello", content="<div>Hello <strong>world</strong></div>")
post.save()
post.content = "<div>Revised</div>"
post.save()
post.update(summary="<em>A short summary</em>")
```

Assignment remains local until the owner is saved. Rich text saves in the owner's
transaction and is available in save/commit callbacks. Failed validation retains
the submitted content for correction and form redisplay. Omitting an attribute
from an update preserves it; assigning `None` or `""` explicitly clears it.
Presence validation rejects visually empty content, including `<div><br></div>`.

Destroying the owner destroys its rich-text rows. Reloading discards submitted
rich-text changes and reads the persisted body. Reading an unset attribute
builds an empty body in memory, which saves with its owner; reading alone does
not write to the database.

## Forms and controller parameters

```jinja
{% call(form) form_with(model=post) %}
  {{ form.label("title") }}
  {{ form.text_field("title") }}

  {{ form.label("content") }}
  {{ form.rich_text_area("content", placeholder="Write something…") }}

  {{ form.submit("Save") }}
{% endcall %}
```

The helper connects Trix to an escaped hidden input. It uses the same model
prefix, CSRF protection, and failed-validation values as other form helpers.
The editor has an accessible name from its label; custom controls can supply
`aria-label` or `aria-labelledby`.

Permit the HTML string like an ordinary scalar:

```python
def _post_params(self):
    return self.params.expect(post=["title", "content"])
```

Keep the allowlist fixed. Rich text does not permit arbitrary nested parameters.

## Rendering

Render the attribute directly:

```jinja
{{ post.content }}
```

This produces server-sanitized HTML inside a `<div class="trix-content">`.
Do not add `|safe` or wrap user input in `Markup`. The framework preserves
supported formatting and safe links while stripping executable HTML, unsafe
URLs, arbitrary attributes, and embedded media. Browser-side filtering is not
the security boundary; every HTML rendering uses the server-side sanitizer.

Body methods are available in Python and templates:

```python
post.content.to_plain_text()  # Ordinary text, not HTML-safe
post.content.to_trix_html()  # Sanitized HTML fragment, without the display wrapper
post.content.blank()
post.content.present()
```

Use the attribute itself for HTML display; `to_trix_html()` returns an ordinary
string for editor values or API payloads. Plain text is also escaped normally by
templates. Model JSON responses do not
automatically include rich-text associations. Select fields explicitly in your
model's `__json__()` when exposing them through an API.

## Loading lists

Like Rails, declarations supply named eager-loading scopes:

```python
Post.with_rich_text_content()
Post.where(title="Hello").with_rich_text_content()
Post.with_all_rich_text()
Post.includes("rich_text_content", "rich_text_summary")
```

These remain chainable model queries. Generated index actions preload all
declared rich text to avoid per-record queries. Rich-text attributes are not
scalar columns and cannot be searched with `Post.where(content=...)`.

## Tests

Scaffold fixtures accept HTML inline:

```yaml
one:
  title: Hello
  content: "<div>Hello <strong>world</strong></div>"
```

In a `SystemTest`, use the editor's label:

```python
self.fill_in_rich_text_area("Content", with_="<div>Hello <strong>world</strong></div>")
self.click_on("Save")
self.assert_selector(".trix-content strong", text="world")
```

The helper accepts HTML through Trix's editor API. Ordinary keyboard input also
works through the underlying Playwright page.

## Scope and Rails differences

The application workflow follows Action Text: declarations, shared storage,
autosaving with the owner, Trix forms, direct rendering, and eager-loading scopes.
This is a bounded first release, not full Action Text compatibility:

- Formatting and links are supported. File uploads, pasted images, attachment
  embeds, and galleries are disabled in the editor and stripped by the server.
  Ordinary model attachments remain available separately.
- An attribute returns an immutable `flaskteroids.rich_text.Content` body, not an
  independently editable rich-text record. Assign through the owner and save it.
- Encryption options, rich-text search, custom attachment rendering, and Rails'
  embed-loading scopes are not implemented.
