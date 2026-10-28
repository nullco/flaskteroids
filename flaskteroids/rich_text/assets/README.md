# Bundled rich-text assets

Lexxy 1.0.2: https://github.com/basecamp/lexxy (MIT; see LEXXY-LICENSE).

Unmodified `app/assets/javascript/lexxy.min.js` (installed here as `lexxy.js`)
and the four `app/assets/stylesheets/lexxy*.css` files from the official release:
https://rubygems.org/downloads/lexxy-1.0.2.gem

Release gem SHA-256:
5d0329955071b8b834fe1cf75e5f9cf6a2ad79a5e77c14a58e43d40e33a35030

The Rails distribution bundles Lexical, DOMPurify, Marked, and Prism rather than
leaving npm dependencies and relative JavaScript chunks for applications to build.
Upstream license notices are preserved in the bundle; additional license texts
are adjacent in LEXICAL-LICENSE, DOMPURIFY-LICENSE, MARKED-LICENSE, and PRISM-LICENSE.
The bundled DOMPurify notice identifies version 3.3.0.

Flaskteroids exposes these assets directly from its installed package. Applications
do not copy or download them. Upgrading the locked Flaskteroids dependency updates
the supplied runtime; precompile production assets and restart the application.
The asset pipeline fingerprints CSS imports as well as the JavaScript.

`rich_text.js`, `rich_text_uploads.js`, and `rich_text.css` are Flaskteroids'
integration. The import-map entry for `@rails/activestorage` supplies only the
DirectUpload transport contract Lexxy consumes, using the existing authorized,
CSRF-protected multipart endpoint. It is not an Active Storage implementation.
Lexxy retains responsibility for progress, attachment cancellation, and native form
validity. No Rails server, editor CDN, or application-side Node toolchain is needed.

To update Lexxy, verify the official gem checksum, replace the upstream runtime
and stylesheets, preserve all dependency licenses, update provenance, and exercise
the rich-text browser and security tests, including fingerprinted production
assets. The runtime's DirectUpload interface is an explicit integration boundary.
