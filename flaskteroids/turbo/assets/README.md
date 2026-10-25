# Bundled Turbo runtime

Unmodified @hotwired/turbo 8.0.23 UMD distribution, MIT licensed.
Source: https://github.com/hotwired/turbo
npm tarball: https://registry.npmjs.org/@hotwired/turbo/-/turbo-8.0.23.tgz

SHA-512 (base64):
GZ7cijxEZ6Ig71u7rD6LHaRv/wcE/hNsc+nEfiWOkLNqUgLOwo5MNGWOy5ZV9ZUDSiQx1no7YxjTNnT4O6//cQ==

Flaskteroids copies this runtime into new applications under app/assets/turbo.
Development and production use the same pinned upstream distribution through the
asset pipeline, without a CDN or JavaScript build toolchain. Browser tests exercise
this application runtime too.

Application-owned copies are preserved by `bin/flask turbo:install`. After a
framework upgrade, review customizations before running `bin/flask turbo:install
--force` and recompile production assets.
