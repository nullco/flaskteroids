# Bundled Turbo runtime

Unmodified @hotwired/turbo 8.0.23 ESM distribution, MIT licensed.
Source: https://github.com/hotwired/turbo
npm tarball: https://registry.npmjs.org/@hotwired/turbo/-/turbo-8.0.23.tgz

Tarball SHA-512 (base64):
GZ7cijxEZ6Ig71u7rD6LHaRv/wcE/hNsc+nEfiWOkLNqUgLOwo5MNGWOy5ZV9ZUDSiQx1no7YxjTNnT4O6//cQ==

The installed Flaskteroids distribution supplies turbo.js to the asset pipeline.
Generated applications pin @hotwired/turbo to turbo.js and import it from
app/javascript/application.js. They do not copy or download the runtime.

Development and production use this same local ESM distribution without a CDN or
Node/build dependency. Production precompilation fingerprints it normally.
Upgrading the locked Flaskteroids dependency upgrades the supplied runtime.

An application can deliberately override turbo.js in app/javascript or
vendor/javascript. Such overrides are application-owned and never overwritten.
Load only one Turbo runtime. The adjacent TURBO-LICENSE covers this file.
