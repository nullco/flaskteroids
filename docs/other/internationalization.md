# Internationalization

Keep application text in YAML catalogs and select a locale around each request or
operation. Flaskteroids provides Rails-style translation keys and helpers without
additional dependencies. This translates application messages, not database content.

## Configure locales

New applications include `config/locales/en.yml`:

```yaml
en:
  hello: "Hello world"
```

Enable the locales your application supports in `config/application.py`:

```python
config.i18n.default_locale = "en"
config.i18n.available_locales = ["en", "es"]
```

The default locale must be available. Locale identifiers are application-defined,
case-sensitive strings, such as `en`, `es`, or `pt-BR`; there is no bundled language
database. Merely adding a catalog does not enable a locale.

Catalogs are UTF-8 `.yml` or `.yaml` files under `config/locales`, including nested
directories. Each file starts with one or more locale mappings. The filename does
not select the locale:

```yaml
# config/locales/products.yml
en:
  products:
    index:
      title: "Products"
    create:
      notice: "Product created"
es:
  products:
    index:
      title: "Productos"
    create:
      notice: "Producto creado"
```

Files merge in sorted path order, with later values overriding earlier values.
Use nested string keys rather than dots in YAML keys. Translation values are
strings; string/null lists are supported for calendar names. Quote keys such as
`"on"`, `"off"`, `"yes"`, and `"no"`, which YAML otherwise interprets as booleans.
YAML is loaded safely, without executable objects.

Change the directory with `config.paths.locales`. Catalogs load on first use and
are cached per application/process. Restart after editing, or call
`reload_translations()` from `flaskteroids.i18n` inside an application context.
A failed reload raises `TranslationError` and leaves the previous catalog intact.
Configuration changes require an application restart.

## Translate text

In Python:

```python
from flaskteroids.i18n import t, with_locale

with with_locale("es"):
    title = t("products.index.title")  # Productos

english = t("products.index.title", locale="en")
```

`t` is an alias for `translate`. Both require an application context. An explicit
`locale=` applies only to that call. `get_locale()` returns the current selection,
or the configured default.

In Jinja:

```html
<h1>{{ t("products.index.title") }}</h1>
```

In `app/views/products/index.html`, a relative key uses the template context:

```html
<h1>{{ t(".title") }}</h1>
```

An included `products/_row.html` uses `products.row` as its relative scope.
Jinja inheritance and imported macros can share the caller's context; use fully
qualified keys in shared layouts and macros rather than relying on their filenames
for relative lookup. Imported macros need `with context` to receive request and
application helpers.

Controllers also expose `self.t` / `self.translate`. Relative keys use the current
controller and action:

```python
# Inside ProductsController.create:
self.redirect_to(self.products_path(), notice=self.t(".notice"))
```

Other Python code uses absolute keys or an explicit string scope:

```python
t("index.title", scope="products")
```

### Interpolation

Keep the whole message in the catalog so translators can reorder its parts:

```yaml
en:
  greeting: "Hello %{name}!"
es:
  greeting: "¡Hola %{name}!"
```

```html
{{ t("greeting", name=user.name) }}
```

Missing interpolation arguments raise `MissingInterpolationArgument`. Replacement
values are not interpreted again as translation placeholders. `locale`, `scope`,
`default`, and `count` are helper options; `count` is also available for interpolation.

### Missing translations and fallbacks

By default, a missing key produces diagnostic text, such as
`translation missing: es.products.index.title`. Supply a literal default when
appropriate:

```python
t("navigation.help", default="Help")
```

To raise `MissingTranslation` instead, enable this setting, particularly in tests:

```python
config.i18n.raise_on_missing_translations = True
```

Fallbacks are disabled by default. Set `config.i18n.fallbacks = True` to look up
missing keys in the configured default locale. Regional fallback chains and
per-locale fallback mappings are not implemented. Defaults and fallback translations
still support interpolation. Invalid locales always raise `InvalidLocale`, rather
than falling back silently.

## Select the request locale

Like Rails, Flaskteroids leaves the selection policy to the application. It does
not automatically trust a query parameter, cookie, or `Accept-Language` header.
Use an around callback in `ApplicationController` to choose and restore the locale:

```python
from flask import current_app

from flaskteroids.actions import around_action
from flaskteroids.controller import ActionController
from flaskteroids.i18n import InvalidLocale, with_locale


class ApplicationController(ActionController):
    def _switch_locale(self):
        selected = self.params.get("locale") or current_app.config.i18n.default_locale
        try:
            with with_locale(selected):
                yield
        except InvalidLocale:
            self.head(400)

    around_action("_switch_locale")
```

`with_locale` restores the previous locale after success, errors, redirects, and
nested scopes. Locale state is isolated between requests, application contexts,
and concurrent execution contexts. Each new request starts at its application's
default, even if its caller has selected another locale.

Preserve a query-based choice explicitly in generated links:

```html
{{ link_to("Español", products_path(locale="es")) }}
```

Route helpers accept query options, but do not automatically propagate the locale.
New layouts set `<html lang="{{ get_locale() }}">`; add this to existing layouts
when adopting internationalization.

## Pluralization

A translation can contain alternatives selected by `count`:

```yaml
en:
  inbox:
    zero: "No messages"
    one: "One message"
    other: "%{count} messages"
```

```python
t("inbox", count=0)  # No messages
t("inbox", count=1)  # One message
t("inbox", count=5)  # 5 messages
```

The basic rule follows Rails' simple backend: use `zero` for zero when provided,
`one` when the count equals one, and `other` otherwise. Counts must be finite
integers, floats, or `Decimal` values, not booleans or numeric strings. Missing
plural forms raise `TranslationError`.

This basic rule is not linguistically correct for every language. Register a
callable for each locale requiring different rules in application configuration:

```python
def japanese_plural(count):
    return "other"


# Inside Application.configure:
config.i18n.pluralization_rules = {"ja": japanese_plural}
```

Enable `ja` in `available_locales` and provide `other` entries in its catalog.
Callables return a catalog form key such as `one`, `few`, `many`, or `other`.
An explicit `zero` entry still takes precedence at zero. Applications own these
rules; Flaskteroids does not bundle comprehensive language-specific plural data.
Fallback translations use the rule belonging to the locale that supplied them.
Word inflection (`person` → `people`) remains separate from message selection.

## HTML translations

Ordinary translations and interpolated values are escaped by Jinja:

```yaml
en:
  greeting: "<strong>Hello %{name}</strong>"
  greeting_html: "<strong>Hello %{name}</strong>"
```

```html
{{ t("greeting", name=user.name) }}
{{ t("greeting_html", name=user.name) }}
```

The first prints literal HTML text. In an autoescaped HTML template, keys ending
in `_html`, or whose last segment is `html`, allow application-authored markup.
Interpolated values are still escaped unless explicitly trusted `Markup` values
are supplied. Never mark user input trusted. Literal `default=` strings are escaped.

Catalog HTML is trusted application source, not sanitized user content. This
convention does not validate links or make translations safe inside JavaScript,
CSS, or URL attributes. Use it in HTML text content.

Python/controller translations return ordinary strings, even for `_html` keys.
Text templates interpolate plain text without HTML escaping. Do not use `|safe`
to make ordinary translations render as HTML.

## Localize dates and times

Use `localize` or its alias `l` in Python, controllers, or templates:

```python
from datetime import date

from flaskteroids.i18n import l

l(date(2026, 3, 2))  # 2026-03-02 in English
l(date(2026, 3, 2), format="long")  # March 02, 2026
```

```html
{{ l(product.created_at, format="short") }}
```

English includes `default`, `short`, and `long` formats and calendar names. Supply
other languages in the application catalog:

```yaml
es:
  date:
    formats:
      default: "%d/%m/%Y"
      long: "%-d de %B de %Y"
    month_names: [null, enero, febrero, marzo, abril, mayo, junio, julio, agosto, septiembre, octubre, noviembre, diciembre]
  time:
    formats:
      default: "%d/%m/%Y %H:%M"
      short: "%H:%M"
```

Dates use `date.formats`; both `datetime` and `time` use `time.formats`. For a
time-only object, provide a time-only format such as `format="%H:%M"` or a matching
named format; the default English time formats include dates. A `format=` containing
`%` is used directly instead of looking up a named format.

Supported directives are `%Y`, `%y`, `%m`, `%d`, `%e`, `%j`, `%H`, `%I`, `%M`, `%S`,
`%f`, `%z`, `%Z`, `%w`, `%u`, `%%`, and these catalog-backed names:

| Directive | Catalog entry |
| --- | --- |
| `%A`, `%a` | `date.day_names`, `date.abbr_day_names` (seven entries, Sunday first) |
| `%B`, `%b`, `%h` | `date.month_names`, `date.abbr_month_names` (13 entries, starting with null) |
| `%p`, `%P` | `time.am`, `time.pm` (upper/lower case respectively) |

A `-` flag removes numeric zero padding, as in `%-d`. Locale-dependent composite
formats such as `%c`, `%x`, and `%X` are rejected rather than consulting Python's
process-global locale. Missing formats/names always raise `MissingTranslation`;
malformed catalog data raises `TranslationError`. Formatting preserves the value's
timezone; it does not perform timezone conversion.

## Mail and jobs

Compose a mailer action inside the desired locale:

```python
with with_locale("es"):
    NoticesMailer().welcome(user).deliver_later()
```

The message captures the locale when `mail()` is called, alongside its recipients
and subject. Both immediate and queued delivery render templates and mailer helpers
in that locale, restoring the delivery context afterward. Mail subjects can use
`t(...)` from Python; mail templates use the same Jinja helpers as controller views.
A relative key in `notices_mailer/welcome.html` resolves under
`notices_mailer.welcome`.

General jobs do not yet capture locale automatically. Pass it as an ordinary job
argument and use `with_locale(locale)` inside `perform`. Do not assume a worker
inherits the request's locale.

## Current boundary

This foundation does not yet translate built-in validation messages, model or
attribute names, form labels, or generated scaffold prose. It does not select
localized template variants or format numbers/currencies. Existing custom
validation messages and error serialization are unchanged. Additional Rails I18n
features, such as namespace lookup, translation-key aliases, and fallback chains,
are not implied by the shared helper names.
