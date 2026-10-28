# Turbo Frames and Streams

Turbo Drive handles browser navigation and form submissions; earlier generated
apps already loaded Turbo from a CDN. Flaskteroids adds Rails-style **Frames**
and **HTTP Stream responses** on the server. No subscriptions, broadcasts,
Action Cable, Stimulus, Node, or JavaScript build tooling are included.

## Install or upgrade

New browser applications include Turbo **8.0.23** through `flaskteroids-turbo`
and load it through [import maps](../other/importmaps.md), without a CDN or runtime
download. The layout includes a CSRF meta token.

For an existing application:

```sh
uv add 'flaskteroids-turbo>=0.1.0,<0.2'
bin/flask turbo:install
```

The command creates missing import-map conventions without replacing application
configuration or JavaScript. It adds the module helper to layouts without script
tags; customized script layouts are left unchanged with setup instructions.
An explicit application `turbo.js` asset overrides the framework version.
Ensure the layout contains:

```html
<meta name="csrf-token" content="{{ csrf_token() }}">
{{ javascript_importmap_tags() }}
```

Load **one** Turbo runtime: replace an existing runtime rather than adding a
second one. Run [asset precompilation](../other/assets.md#production-builds) for
production. Installation does not rewrite existing page views. To upgrade Turbo:

```sh
uv lock --upgrade-package flaskteroids-turbo
uv sync --locked
bin/flask assets:precompile
```

## Frames and layouts

A frame navigation replaces only the matching `<turbo-frame>` in the current
page. Its destination must return a frame with the **same ID**.

New generated page templates use:

```html
{% extends layout %}
{% block body %}
  <!-- Page content, including any frames. -->
{% endblock %}
```

`layout` selects `layouts/application.html` normally and
`layouts/turbo/frame.html` for a request carrying `Turbo-Frame`. The minimal frame
layout retains `head` and `body` blocks and the CSRF meta token. Override it in
`app/views/layouts/turbo/frame.html` if needed. Set `Controller.layout` or
`frame_layout` to another template path on a controller class, or assign
`self.layout` / `self.frame_layout` in an action or callback before rendering.

Existing `{% extends "layouts/application.html" %}` templates still work: Turbo
extracts the matching frame from the full page. Adopting `{% extends layout %}`
is an optional rendering optimization, not a requirement for Frames.

Controllers expose `self.turbo_frame_request` (a boolean) and
`self.turbo_frame_request_id` (the ID or `None`). Templates call
`turbo_frame_request()` and `turbo_frame_request_id()` instead.

### IDs and frame tags

`dom_id`, `dom_class`, `turbo_frame_tag`, and `turbo_stream` are automatically
available in Jinja. Python code can import them and the builder class:

```python
from flaskteroids.turbo import (
    TurboStreamBuilder,
    dom_class,
    dom_id,
    turbo_frame_tag,
    turbo_stream,
)
```

For a `Post` with key `1`, `dom_id(post)` is `post_1`,
`dom_id(post, "edit")` is `edit_post_1`, and `dom_class(post)` is `post`.
A record without a key, or the `Post` class, gives `new_post`;
`dom_id(Post, "edit")` gives `edit_post`. Keys come from public `Model.to_key()`,
not an overridden URL slug in `to_param()`. `to_key()` and `to_partial_path()` can
be overridden for custom record identity and partial conventions.

```html
{% call turbo_frame_tag(post) %}{{ post.title }}{% endcall %}
{% call turbo_frame_tag(post, "edit") %}...{% endcall %}
{% call turbo_frame_tag("post", "1", "comments") %}...{% endcall %}

{% call turbo_frame_tag("preview", src=post_path(post), loading="lazy", target="_top") %}
  Loading…
{% endcall %}
```

The compound ID above is `post_1_comments`. `src` also accepts a model destination,
such as `src=post` or `src=[post, comment]`. A lazy frame fetches its source when
visible; `target="_top"` makes navigation leave the frame.

Links and forms can target a frame, or opt out of Turbo:

```html
{{ link_to("Edit", edit_post_path(post), data={"turbo_frame": dom_id(post)}) }}
{{ link_to("Full page", post_path(post), data={"turbo_frame": "_top"}) }}
{% call(form) form_with(model=post, data={"turbo": False}) %}
  {{ form.text_field("title") }}
  {{ form.submit("Save") }}
{% endcall %}
```

Frame/Stream tags, links, buttons, and `form_with` normalize `class_` to `class`,
nested `data`/`aria` keys to dashed attributes, and HTML boolean attributes such as
`disabled=True` appropriately.
`data={"turbo": False}` emits `data-turbo="false"`, not an omitted attribute.
Ordinary text and all attribute values are escaped. Use `Markup` only for trusted
HTML; never apply `|safe` to user input.

### Minimal inline edit

Assume `route.resources("posts")` and a `Post` model with a `title` attribute.
Use a record partial that is itself the frame, so rendering it in a list or a
show page does not create duplicate DOM IDs:

```html
<!-- app/views/posts/_post.html -->
{% call turbo_frame_tag(post) %}
  <p>{{ post.title }}</p>
  {{ link_to("Edit", edit_post_path(post)) }}
{% endcall %}
```

```html
<!-- app/views/posts/show.html -->
{% extends layout %}
{% block body %}{{ render(post) }}{% endblock %}
```

```html
<!-- app/views/posts/_form.html -->
{% for message in post.errors.full_messages() %}
  <p>{{ message }}</p>
{% endfor %}
{% call(form) form_with(model=post) %}
  {{ form.label("title") }}
  {{ form.text_field("title") }}
  {{ form.submit("Save") }}
{% endcall %}
```

```html
<!-- app/views/posts/edit.html -->
{% extends layout %}
{% block body %}
  {% call turbo_frame_tag(post) %}
    {{ render(partial="posts/form", locals={"post": post}) }}
    {{ link_to("Cancel", post_path(post)) }}
  {% endcall %}
{% endblock %}
```

```python
# app/controllers/posts_controller.py
from app.controllers.application_controller import ApplicationController
from app.models.post import Post
from flaskteroids.routes import post_path


class PostsController(ApplicationController):
    def show(self):
        self.post = Post.find(self.params["id"])

    def edit(self):
        self.post = Post.find(self.params["id"])

    def update(self):
        self.post = Post.find(self.params["id"])
        if self.post.update(**self.params.expect(post=["title"])):
            return self.redirect_to(post_path(self.post), status=303)
        return self.render("edit", status=422)
```

Show, edit, validation redisplay, and the redirected show all contain the same
`post_1` frame. Return **422** for invalid HTML and use **303 See Other** after a
successful mutation. Ordinary Turbo POST forms support HTML fallback; a Stream
response is not required. Generated scaffolds remain full-page CRUD by default,
not inline-edit interfaces. New scaffold record IDs use `dom_id` underscores,
and generated update redirects use 303.

## HTTP Stream responses

Streams can change several elements in one response, without a frame wrapper.
Turbo forms advertise `text/vnd.turbo-stream.html` for unsafe submissions. GET
links/forms opt in with `data={"turbo_stream": True}`:

```html
{{ link_to("Load more", posts_path(page=2), data={"turbo_stream": True}) }}
```

### Create: append a post and update a notice

Add an index with a target container and the create form:

```html
<!-- app/views/posts/index.html -->
{% extends layout %}
{% block body %}
  <div id="notice"></div>
  <div id="posts">
    {% for post in posts %}{{ render(post) }}{% endfor %}
  </div>
  {{ render(partial="posts/form", locals={"post": post}) }}
{% endblock %}
```

Add these actions to `PostsController` (the preceding imports still apply):

```python
def index(self):
    self.posts = Post.all()
    self.post = Post.new()

def create(self):
    self.post = Post.new(**self.params.expect(post=["title"]))
    if self.post.save():
        return self.respond_to(
            html=lambda: self.redirect_to(post_path(self.post), status=303),
            turbo_stream=lambda: self.render(),
        )
    return self.render("new", status=422)
```

The HTML validation fallback needs `app/views/posts/new.html`:

```html
{% extends layout %}
{% block body %}
  {{ render(partial="posts/form", locals={"post": post}) }}
{% endblock %}
```

The successful Stream response uses the conventional template, **without page
layout inheritance**:

```html
<!-- app/views/posts/create.turbo_stream.html -->
{{ turbo_stream.append("posts", post) }}
{{ turbo_stream.update("notice", "Post created") }}
```

`post` renders through `posts/_post.html`, which supplies its own frame ID.
The non-Turbo HTML request redirects normally. A normal Turbo form can redisplay
`new.html` with 422 when no `new.turbo_stream.html` exists and HTML is acceptable.

### Builder and partials

`turbo_stream` in templates and `self.turbo_stream` in controllers provide:

- `append`, `prepend`, `before`, `after`, `replace`, `update`, and `remove`.
  Each accepts an element ID or record target. Their `*_all` variants accept a
  CSS selector instead, for example `remove_all(".expired")`.
- `replace` and `update` support `method="morph"`.
- `action(name, target, ...)` and `action_all(name, selector, ...)` build generic
  actions; custom browser actions still need application JavaScript.
- `refresh()` emits a page-refresh action, forwarding `X-Turbo-Request-Id` when
  present. Use `refresh(request_id="...")` to override it, or `request_id=None`
  to omit it. `remove` and `refresh` emit no `<template>` content.

```html
{{ turbo_stream.replace(post) }}
{{ turbo_stream.update("notice", partial="shared/notice", locals={"message": "Saved"}) }}
{{ turbo_stream.replace(post, method="morph") }}
{% call turbo_stream.update("notice") %}
  <strong>Saved {{ post.title }}</strong>
{% endcall %}
```

Omitted content on a record target infers its conventional partial. Explicit
record content, as in `append("posts", post)`, does the same. Ordinary string
content is escaped; rendered partials and Jinja call blocks supply trusted HTML.

The template/helper `render` API supports all of these forms:

```html
{{ render(post) }}
{{ render(partial="posts/post", locals={"post": post}) }}
{{ render("exact/file.html", post=post) }}
```

`render(post)` uses `post.to_partial_path()` (normally `posts/post`) and assigns
`post` inside `posts/_post.html`. Explicit locals override inferred values.
These calls share the current view's helper context. They render HTML, **not a
controller response**; application helpers can call them as `self.render(...)`.

Build a response directly when a separate Stream template is unnecessary:

```python
return self.render(turbo_stream=self.turbo_stream.remove(self.post))
# Or multiple operations in order (a list or tuple):
return self.render(turbo_stream=[
    self.turbo_stream.remove(self.post),
    self.turbo_stream.update("notice", "Post removed"),
])
```

Choose one return above, not both: the usual single-response lifecycle applies.

### Negotiation and routes

`self.respond_to(html=..., json=..., turbo_stream=...)` selects an offered format.
An implicit render selects `<action>.turbo_stream.html` when Streams are requested;
it falls back to `<action>.html` if the Stream template is absent and HTML is
acceptable. Stream responses use MIME type `text/vnd.turbo-stream.html`.

Accept quality values are honored. Equal-quality requests explicitly listing
Streams use client format order; wildcard-only requests default to HTML. A
request with no acceptable offered format returns **406**. Resource helpers accept
`posts_path(format="turbo_stream")` or
`post_path(post, format="turbo_stream")` to force Streams via a `.turbo_stream`
suffix; forced URLs require a Stream response rather than HTML fallback.
Custom named routes do not automatically gain suffix support. See
[Routing](../controllers/routing.md#response-formats).

Relative translations in `posts/create.turbo_stream.html`, such as `t(".notice")`,
use `posts.create.notice`: the format suffix is not part of the translation scope.

## Caching and security

Controller HTML, JSON, and Stream responses vary on `Accept` and `Turbo-Frame`.
For the application's framework response class, validators set with `set_etag`
or `add_etag` track the original value and are partitioned by **final MIME type**
and **frame/page** before `make_conditional` and final emission. Validators set
on pending `self.response` transfer into the prepared response with that original
value, so changing from HTML to JSON or Streams does not reuse an HTML validator.

This does not create validators or perform conditional handling automatically:
set a validator and call `response.make_conditional(request)` yourself when
needed. Manually constructed native Flask/Werkzeug `Response` objects and manually
assigned `ETag` header strings remain application-owned and are **not rewritten**;
provide representation-specific validators for those responses yourself.

These cache boundaries are not authorization or a shared-cache policy. A
`Turbo-Frame` header is not proof of permission. Keep normal authentication,
authorization, [strong parameters and CSRF protection](../other/forms.md), and do
not put session-specific pages or CSRF tokens in a shared cache.
