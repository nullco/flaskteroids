# Add login and product images

The catalog from [Getting started](../getting_started.md) lets anyone change
products. In this part of the store tutorial, you will require login for changes
and add a product photo to the existing form.

After working through this guide, you will know how to:

- Generate a login workflow and keep browsing public.
- Attach an image and accept it through a model-backed form.
- Add styles and prepare assets for production.

Continue in the same `store` application, after completing Getting started.
Keep the products you created there, and run commands from the application root.

## Require login to change products

Right now, anyone can create, edit, or delete products. Stop the server and run:

```sh
bin/flask generate authentication
bin/flask db:migrate
```

The generator adds `User` and `Session` models, login/logout and password-reset
controllers, templates, mailers, routes, and tests. It also adds an
`Authentication` concern to `ApplicationController`, making authentication the
default for its subclasses. There is no public sign-up form.

Open `bin/flask shell` and create your own account:

```python
from getpass import getpass

password = getpass("Choose a password: ")
user = User.create(
    email_address="you@example.org",
    password=password,
    password_confirmation=password,
)
assert not user.errors, user.errors.full_messages()
del password
exit()
```

`has_secure_password()` hashes the password; the database stores a digest, not
its plaintext. Use a real password of your own, and do not put it in source code.

Restart the server and visit <http://127.0.0.1:5000/products/new>. You should be
redirected to the login page at `/session/new`. Log in with your account.

### Keep the catalog public

Visitors should still be able to browse products without an account. In
`app/controllers/products_controller.py`, add `skip_before_action` to the
existing actions import:

```python
from flaskteroids.actions import before_action, skip_before_action
```

Replace the existing callback declaration inside `ProductsController` with
these two class-body calls, keeping its methods unchanged:

```python
    skip_before_action("_require_authentication", only=["index", "show"])
    before_action("_set_product", only=["show", "edit", "update", "destroy"])
```

The generated `Authentication` concern provides the `is_authenticated()` template
helper. It resumes the session when needed, including on public pages where
`_require_authentication` is skipped. No extra callback or controller variable
is needed.

### Show login and logout controls

Use the generated singular session resource for logout. Its `session_path()`
destination accepts POST for login and DELETE for logout; `button_to` renders
the browser-safe POST form, hidden DELETE override, and CSRF token. No extra
logout endpoint or JavaScript is needed.

In `app/views/products/index.html`, replace the New product link with:

```html
{% if is_authenticated() %}
  {{ link_to("New product", new_product_path()) }}
  {{ button_to("Log out", session_path(), method="DELETE") }}
{% else %}
  {{ link_to("Log in", new_session_path()) }}
{% endif %}
```

In `app/views/products/show.html`, wrap the Edit and Delete controls:

```html
{% if is_authenticated() %}
  {{ link_to("Edit", edit_product_path(product)) }}
  {{ button_to("Delete", product, method="DELETE") }}
{% endif %}
```

Hiding controls is not access control: the controller callback protects the
write actions even if someone sends a request directly. This example has one
role: every account can manage the catalog. Ownership checks, permissions, and
public registration need additional application rules.

Log out and verify that browsing still works, while `/products/new` requires
login again. Password reset also needs working mail delivery before real users
can rely on it.

**Checkpoint:** guests can browse the catalog, but only signed-in users can
create, edit, or delete products. Keep the account you created: we'll use it to
manage inventory shortly. We'll add automated checks after building the features.

## Upload product images

A shopper can browse the catalog, but an image makes a product easier to
recognize. Let's add a photo without changing the product's ordinary edit flow.
Install the attachment tables and configuration:

```sh
bin/flask attachments:install
bin/flask db:migrate
```

Stop and restart the server after this migration, as with other schema changes.

In `app/models/product.py`, import `has_one_attached` alongside `validates`, then
update the declarations inside `Product` to:

```python
    validates("name", presence=True)
    has_one_attached(
        "featured_image",
        max_size=2 * 1024 * 1024,
        content_types=["image/png", "image/jpeg"],
    )
```

The attachment is not an extra column on `products`: the attachment tables keep
track of files and their owning records.

Inside the `form_with` block in `app/views/products/_form.html`, before the submit
button, add:

```html
<div>
  {{ form.label("featured_image") }}
  {{ form.file_field("featured_image", accept="image/png,image/jpeg") }}
</div>
```

`form_with` detects the file field and adds multipart encoding. Permit the upload
by replacing `_product_params()` in `ProductsController` with:

```python
    def _product_params(self):
        return self.params.expect(product=["name", "description", "featured_image"])
```

In the `body` block of `app/views/products/show.html`, add:

```html
{% if product.featured_image.attached() %}
  <img src="{{ blob_path(product.featured_image) }}" alt="{{ product.name }}">
{% endif %}
```

Log in, edit a product, and upload a small PNG or JPEG. After saving, its show
page should display the image. Reopen Edit and save without selecting another
file: the existing image should remain. Files become available after the save
commits.

Development uses local disk storage. Signed download links are accessible to
anyone who has the link by default, which suits public catalog images but not
private documents. Content-type checks are not file scanning. See
[Attachments](../other/attachments.md) for storage services, authorization, request
size limits, and cleanup jobs.

## Give the store a little polish

The generated layout already includes `app/assets/stylesheets/application.css`.
Replace or extend that file with:

```css
body {
  font-family: system-ui, sans-serif;
  max-width: 60rem;
  margin: 2rem auto;
  padding: 0 1rem;
}

form div {
  margin: 1rem 0;
}

label {
  display: block;
}

img {
  max-width: 100%;
  height: auto;
}

.errors {
  color: #b91c1c;
}
```

Refresh a product page to see the change. Development serves source assets
directly. Production uses fingerprinted files, built with:

```sh
bin/flask assets:precompile
```

Docker builds run this compilation automatically. Keep the generated output and
manifest together; production has no fallback to source files.

The generated layout loads `app/javascript/application.js` through import maps.
That entrypoint imports the local Turbo runtime supplied by the installed
Flaskteroids package; no CDN or application-owned runtime copy is needed.
Production precompilation fingerprints JavaScript like other assets. Add packages
with `bin/importmap pin PACKAGE`; the compiler does not bundle JavaScript or
compile Sass. See [Import maps](../other/importmaps.md) and [Assets](../other/assets.md).

## Next steps

You can now manage the catalog behind a login and display product photos.
Continue with [Restock notifications](restock_notifications.md) to connect
associations, callbacks, background jobs, and email.
