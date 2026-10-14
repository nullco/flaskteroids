# Assets

Flaskteroids uses Flask's built-in `static` endpoint at `/assets/`:

| Environment | Served directory |
| --- | --- |
| Development/test | `app/assets` — source files, no build required |
| Other environments | `public/assets` — fingerprinted build output |

Flask handles delivery, MIME types, ETags, conditional requests, HEAD, and ranges.
Directory structure is preserved in URLs.

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

Helpers generate source URLs in development and manifest-resolved URLs in
production. Standard `url_for("static", filename=...)` still works but does not
resolve fingerprints.

## CSS references

Use ordinary file-relative paths. In `stylesheets/application.css`:

```css
@import "themes/base.css";
.hero { background-image: url("../images/logo.png"); }
@font-face { font-family: Demo; src: url("../fonts/demo.woff2"); }
```

All non-hidden asset subdirectories, including `fonts/`, are included.
Compilation rewrites local URLs/imports to fingerprinted files, preserving
queries/fragments. Image/font changes also fingerprint dependent stylesheets.
Missing references and CSS cycles fail before replacing the previous manifest.

The dependency-free rewriter supports standard quoted/unquoted `url(...)`,
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

These commands compile without application boot, database access, runtime keys,
or initializers. Plain `flask assets:precompile` loads the app first.

Deploy the output directory with its `.manifest.json`. Builds are deterministic;
helpers raise `AssetError` for missing/invalid manifests, missing entries, or
missing compiled files. There is no source fallback. Docker includes compilation
and retains output; generated Git/Docker exclusions omit build artifacts.

Flask serves the output directory directly, not a manifest allowlist. Old
fingerprints remain usable after builds; compilation does not delete them.
Keep only intended public files in asset directories. Hidden paths and symlinks
are rejected; missing/unsafe HTTP requests return 404.

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

These select Flask's `static_folder` and `static_url_path` before registering
its `static` route, which calls `app.send_static_file` directly. Paths are
project-root-relative, must stay inside the project, and cannot overlap.
One source root contains all asset types. URL prefixes must be absolute paths
without query strings; trailing slashes are normalized.

For example, use `source_path = "frontend"`, `output_path = "static"`, and
`prefix = "/rails/assets"` to change the directories and URL independently.
The bootless compiler does not read Python configuration; pass matching paths:

```sh
bin/flask assets:precompile --source frontend --output static
```

Exclude custom output directories from Git/Docker input and regenerate them in
the build. Helpers respect deployment script prefixes.

For reverse-proxy delivery, serve the output at the configured prefix and set
`config.assets.serve = False`; URL generation remains available. Configure MIME
and cache headers, block dotfiles (including the manifest) and symlinks, and
never expose source/project directories.
