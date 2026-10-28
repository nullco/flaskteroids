# Rich-text integration assets

`rich_text.js`, `rich_text_uploads.js`, and `rich_text.css` are Flaskteroids'
editor integration. The upstream runtime and stylesheets live in
`flaskteroids-lexxy`.

The import-map entry for `@rails/activestorage` supplies only the DirectUpload
transport contract Lexxy consumes, using the existing authorized, CSRF-protected
multipart endpoint. It is not an Active Storage implementation. Lexxy handles
progress, attachment cancellation, and native form validity.
