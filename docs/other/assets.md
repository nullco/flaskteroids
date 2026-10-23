# Assets

Put stylesheets, images, and fonts in `app/assets`. They work without a build in
development. For production, precompile them into files with content hashes in
their names, so browsers can cache them safely.

Flaskteroids serves assets at `/assets/` using Flask's `static` endpoint:

| Environment | Served directory |
| --- | --- |
| Development/test | `app/assets` — source files, no build required |
| Other environments | `public/assets` — fingerprinted build output |

URLs keep the asset directory structure. Flask handles file delivery, content
types, conditional requests, HEAD requests, and byte ranges.

## Helpers

Generated layouts already link `app/assets/stylesheets/application.css`:

```html
{{ stylesheet_link_tag("application", **{"data-turbo-track": "reload"}) }}
<img src="{{ asset_path("logo.png") }}" alt="Logo">
```

Helpers are also available from `flaskteroids.helpers`. `stylesheet_link_tag`
appends `.css`, accepts multiple names and escaped HTML attributes, and returns
trusted markup.

Names are relative to the source root, such as `stylesheets/application.css`.
Short names search immediate subdirectories: `application.css` and `logo.png`
resolve into `stylesheets/` and `images/`. Ambiguous names raise `AssetError`;
use directory-qualified names to disambiguate.

Helpers generate source URLs in development. In production, they read the build
manifest to find the fingerprinted filename. A **fingerprint** is a content hash:
when a file changes, its URL changes too.

Native `url_for("static", filename=...)` works, but does not look up fingerprints.

## CSS references

Use ordinary file-relative paths. In `stylesheets/application.css`:

```css
@import "themes/base.css";
.hero { background-image: url("../images/logo.png"); }
@font-face { font-family: Demo; src: url("../fonts/demo.woff2"); }
```

Precompilation includes all non-hidden asset subdirectories, including `fonts/`.
It rewrites local CSS URLs and imports to point to fingerprinted files, keeping
query strings and fragments. Changing an image or font also changes the
fingerprint of stylesheets that reference it.

Missing references or circular CSS dependencies fail the build before replacing
the previous manifest.

### CSS support and limits

The URL rewriter supports standard quoted/unquoted `url(...)`,
quoted `@import`, and normal CSS escapes in UTF-8 files. Comments, ordinary
strings, external/data/absolute URLs, and fragment-only references stay unchanged.
It is not a full CSS parser: escaped function names and string-only `image-set()`
references are unsupported; use `url(...)` for those references. There is no
Sass/JavaScript compilation, bundling, or minification.

## Production builds

```sh
bin/flask assets:precompile
# From outside the application:
flaskteroids assets:precompile --root /path/to/app
```

Both commands build without starting the application, accessing the database,
reading runtime keys, or running initializers. By contrast, plain
`flask assets:precompile` loads the application first.

Deploy `public/assets` **including its `.manifest.json` file**. Generated Docker
builds already precompile assets and keep the output in the image; generated
ignore files exclude local build artifacts from Git and Docker input.

Builds are deterministic. If the manifest, an entry, or a compiled file is missing
or invalid, helpers raise `AssetError`; production does not fall back to source
files.

### Public files and caching

**Everything in the served asset directory should be public.** The manifest is a
filename lookup, not an access-control list. Builds leave old fingerprinted files
in place, so old URLs remain usable. Hidden paths and symlinks are rejected;
missing or unsafe requests return 404.

Generated production configuration sets Flask's `SEND_FILE_MAX_AGE_DEFAULT`
to one year; successful compiled responses with positive cache lifetimes are
also immutable. Set the native option to `None` for conditional revalidation or
`0` for immediate revalidation. Without this configuration, Flask defaults to
revalidation. The option also affects other `send_file()` calls without an
explicit cache lifetime.

## Configuration

```python
config.assets.source_path = "app/assets"
config.assets.output_path = "public/assets"
config.assets.prefix = "/assets"
config.assets.serve = True
```

Set these options in application configuration. Source and output paths are
relative to the project root, must remain inside the project, and cannot overlap.
One source directory holds every asset type. The URL prefix must be an absolute
path with no query string; trailing slashes are normalized.

Internally, these options configure Flask's `static_folder` and `static_url_path`
before its static route is registered. Delivery uses `app.send_static_file`.

For example, use `source_path = "frontend"`, `output_path = "static"`, and
`prefix = "/custom/assets"` to change the directories and URL independently.
The bootless compiler does not read Python configuration; pass matching paths:

```sh
bin/flask assets:precompile --source frontend --output static
```

Exclude custom output directories from Git/Docker input and regenerate them in
the build. Helpers respect deployment script prefixes.

### Serve through a reverse proxy

To let a reverse proxy deliver files, serve the output at the configured prefix and set
`config.assets.serve = False`; URL generation remains available. Configure MIME
and cache headers, block dotfiles (including the manifest) and symlinks, and
never expose source/project directories.
