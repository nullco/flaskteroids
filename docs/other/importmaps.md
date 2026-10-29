# JavaScript with import maps

Write browser-native JavaScript modules without Node, npm installation, bundling,
or transpilation. Flaskteroids follows Rails' import-map workflow: declare logical
module names, import them from JavaScript, and let the asset pipeline supply
development or fingerprinted production URLs.

Browser applications include this setup. `bin/flask importmap:install` restores
missing conventions without replacing application code.
It adds the module helper to layouts without script tags; customized script layouts
are left unchanged with setup instructions. Keep only one Turbo runtime.

## Application entrypoint

`app/javascript/application.js` starts with:

```javascript
import "@hotwired/turbo"
```

The generated layout loads it using:

```html
{{ javascript_importmap_tags() }}
```

This emits the inline import map, configured module preloads, and a module script
that imports `application`. The map precedes all module scripts. It is marked
`data-turbo-track="reload"`, so Turbo performs a full reload when a subsequent
page has a changed map.

## Pins and local modules

Configuration is trusted Python with an explicit registration callback:

```python
# config/importmap.py
def register(importmap):
    importmap.pin("application")
    importmap.pin("@hotwired/turbo", to="turbo.js")
    importmap.pin_all_from("app/javascript/lib", under="lib")
```

Then create `app/javascript/lib/greeting.js`:

```javascript
export function greet(name) {
  return `Hello, ${name}`
}
```

And import it in `application.js`:

```javascript
import { greet } from "lib/greeting"

document.addEventListener("turbo:load", () => {
  console.log(greet("Flaskteroids"))
})
```

A pin defaults to `NAME.js`; `to=` selects a different logical asset path.
`pin_all_from` recursively registers `.js` and `.mjs` files. A directory's
`index.js` is imported by the directory name: `lib/index.js` becomes `lib`.
An optional `to=` prefix separates asset paths from the logical namespace.

**Use pinned logical imports, not file-relative imports.** For example, use
`"lib/greeting"`, not `"./lib/greeting.js"`. The compiler does not rewrite
JavaScript, so relative filenames will not follow production fingerprints.

Development/test rendering re-evaluates configuration and discovers added or
removed local modules. Refresh the page to use changes; this is not hot module
replacement. Production loads configuration at boot and caches resolved maps;
restart application processes when deploying.

## Third-party packages

```sh
bin/importmap pin @github/hotkey
bin/importmap pin @github/hotkey@3.1.1
bin/importmap pin @github/hotkey --no-preload
```

The command calls JSPM's resolution API with browser/module conditions, downloads
the returned dependencies to `vendor/javascript`, and writes pins into
`config/importmap.py`. Package versions are recorded in pin comments and download
provenance. Commit the configuration **and downloaded files**.

```javascript
import { install } from "@github/hotkey"
```

Package maintenance commands:

```sh
bin/importmap packages          # List downloaded pins and recorded versions
bin/importmap update            # Resolve current versions of downloaded pins
bin/importmap pristine          # Redownload recorded versions
bin/importmap unpin @github/hotkey
bin/importmap json              # Inspect the resolved browser import map
```

`unpin` removes only explicitly named pins and their managed files. It preserves
files referenced by other literal pins and does not automatically prune transitive
dependencies. Remove unused dependency pins explicitly.

`pin`, `update`, and `pristine` accept `--from jspm|unpkg|jsdelivr`; resolution
still uses JSPM's API. `pin --env development` requests development package builds.
No service call is made during application startup or page rendering.

Commands run without application boot, credentials, or database access. From outside
the application, use:

```sh
flask importmap --root /path/to/app pin @github/hotkey
```

Configuration edits are conservative and AST-guided. Commands preserve unrelated
Python and existing pin options, but require literal `importmap.pin("name", ...)`
statements directly inside a multiline `register(importmap)`. Computed, nested,
or compound pin declarations must be edited manually. Arbitrary Python remains
supported at runtime.

Resolution, validation, and downloads complete before files are changed.
Individual file replacements are atomic; the whole operation is not a multi-file
transaction. Automatic vulnerability audits and outdated-package reports are not
included in this initial implementation.

## Packaged Turbo

`flaskteroids-turbo` supplies the pinned Turbo **8.0.23** ESM build. Applications
reference it through the `@hotwired/turbo` pin, rather than copying or downloading
it. Upgrade the locked `flaskteroids-turbo` dependency to update the runtime.

An application can deliberately override `turbo.js` in `app/javascript` or
`vendor/javascript`. Application assets take precedence over the packaged
asset. Keep an override compatible with the framework's Turbo integration.

`bin/flask turbo:install` configures this same import-map workflow; it does not
overwrite or refresh application-owned runtime files.

## Preloads, additional entrypoints, and lazy imports

Pins preload by default, avoiding serial discovery of deeply nested imports.
Disable preloading for an optional module:

```python
def register(importmap):
    importmap.pin("application")
    importmap.pin("editor", preload=False)
    importmap.pin("admin_support", preload="admin")
    importmap.pin("shared_support", preload=["application", "admin"])
    importmap.pin("admin")
```

```javascript
const editor = await import("editor")
```

Use `{{ javascript_importmap_tags("admin") }}` instead of the default helper for
an alternate entrypoint. To load an additional pinned module on one page, put
`{{ javascript_import_module_tag("editor") }}` after the main import-map helper.
`javascript_inline_importmap_tag` and `javascript_module_preload_tag` are also
available for advanced layouts. Do not emit duplicate maps.

## Security, integrity, and caching

All helpers are available from `flaskteroids.helpers` and in Jinja. Inline JSON
and module names are escaped for script-element safety. Helpers accept
`nonce=` for applications managing a Content Security Policy:

```html
{{ javascript_importmap_tags(nonce=csp_nonce) }}
```

Enable optional integrity metadata:

```python
def register(importmap):
    importmap.enable_integrity()
    importmap.pin("application")
    importmap.pin("optional", integrity=False)
    importmap.pin(
        "external",
        to="https://example.com/library-1.0.js",
        integrity="sha384-REPLACE_WITH_REAL_BASE64_HASH",
    )
```

Local SHA-384 hashes cover the actual served bytes, including production assets.
Hashes appear in the map's `integrity` field and applicable preload links.
External hashes are application-supplied. Browser support for import-map integrity
varies; do not assume it universally enforces integrity on lazy-loaded modules.

If manually managing HTML ETags, include `importmap_digest()` in the validator
alongside the page's own cache key. Otherwise an unchanged page validator could
hide changed JavaScript mappings. This helper does not create validators or invoke
conditional handling automatically.

## Production and boundaries

```sh
bin/flask assets:precompile
bin/importmap json --environment production
```

Precompilation includes application JavaScript, downloaded modules, and the
`flaskteroids-turbo` runtime. It is deterministic, offline, and does not boot the app.
Deploy the output with its manifest; the rendered map resolves logical names to
fingerprinted URLs. Changing a dependency updates its mapping without rewriting
the importing JavaScript. See [Assets](assets.md) for custom paths and serving.

`json` accepts `--source`, `--output`, and `--prefix` when inspecting customized
asset configurations; it does not load application settings automatically.

Import maps support modern browsers' native ES modules. They do not compile
TypeScript/JSX, convert arbitrary CommonJS packages, supply Node APIs, rewrite
relative imports or `import.meta.url` assets, manage worker imports, or bundle
JavaScript/CSS. Some packages require additional chunks or remote assets even
after their entrypoints are downloaded. Verify a package's browser compatibility
and complete asset graph rather than assuming arbitrary npm packages work offline.
No legacy-browser shim is installed by default.
