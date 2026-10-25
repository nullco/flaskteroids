---
id: turbo
type: module-design
status: active
title: Rails-style Turbo Frames and HTTP Streams
tags: [views, controllers, turbo]
---

## Responsibility and boundary

Flaskteroids supplies the server-side developer experience of Rails' Turbo Frames
and HTTP Stream responses, adapted to Python and Jinja. The unmodified upstream
Turbo runtime owns browser navigation, frame extraction, stream execution, and
morphing. There is no parallel browser state engine, broadcast transport,
subscription service, Stimulus integration, or JavaScript build toolchain.

Record identity and conventional partial lookup extend the existing model/view
workflow rather than introducing a second model layer. Model `to_key()` exposes
primary-key components independently of persistence state and overridable URL
slugs. `to_partial_path()` supplies the conventional record partial. Generic
HTML/partial rendering is shared below helper discovery and controller response
handling; it must not import either layer to break dependency cycles.

## Application-facing contracts

Frame helpers accept records, classes, prefixes, compound IDs, and standard frame
attributes. `dom_id` uses Rails-style underscore-separated keys and `new_` for
keyless records. Generated record partial IDs follow this convention, but ordinary
scaffolds remain full-page CRUD rather than automatically becoming inline UIs.

Stream builders support standard operations, selector targets, custom actions,
refresh, morph options, blocks, explicit partials/locals, and record inference.
Ordinary text and all attribute values are escaped; rendered templates and
explicitly trusted markup retain HTML. Forms, links, buttons, and Turbo tags share
nested data/aria options, Python trailing-underscore normalization, and boolean
attribute rules. This deliberately replaces the earlier literal `class_` output.

Controller Streams use the existing single-response lifecycle, callbacks, assigns,
and response metadata, not a separate dispatch path. Explicit stream bodies can
contain multiple operations. Negotiation considers offered formats and quality
values; explicit resource suffixes take precedence. Requests explicitly listing
Streams use client order to break concrete-format ties; wildcard-only requests
retain HTML precedence. A selected stream template uses `.turbo_stream.html`,
keeping Jinja HTML autoescaping. Missing stream roots can fall back to accepted
HTML, including 422 form redisplay; explicit stream suffixes force the format.
Errors inside an existing stream template are not missing-root fallbacks.
Relative translations use the logical view path without the format suffix.

## Rendering and execution scope

Jinja explicitly selects its parent template, unlike Rails' controller-owned
layout composition. New page views therefore use `{% extends layout %}`. The
request's view context selects the normal controller layout or the minimal,
application-overridable `layouts/turbo/frame.html`, preserving head contributions.
Literal inheritance remains untouched and works through Turbo's full-page frame
extraction. Request-dependent template-loader substitution is avoided because
Jinja caches compiled templates across requests.

Controller frame predicates and Jinja helpers share request interpretation.
The frame header is rendering metadata, never authentication or authorization.
Normal strong parameters, permission checks, and CSRF protection still apply.
View helpers and nested stream partials share render-local owner state while
remaining isolated between requests, applications, and mail delivery. Layout and
frame context join the existing framework template processor; repeated setup must
not multiply middleware or processors.

## Validators and native response boundary

Frame/page and negotiated MIME variants must not validate against each other's
framework-managed ETags. The application response-class adapter retains original
`set_etag`/`add_etag` values, partitions them using the final MIME and rendering
scope before conditional comparisons, and finalizes them before emission.
Pending controller validators transfer their original value into prepared
responses. This also covers framework response objects whose rendering scope is
established after the validator was assigned.

Rewriting already-published validators only in `after_request` is incorrect:
native `make_conditional` may already have compared a different tag, breaking
304 responses and `If-Match`. Tracking the original value also prevents repeated
hashing and stale HTML validators after JSON/Stream rendering. Existing weak-tag
semantics and custom response subclasses are retained. The integration adds
`Vary: Accept, Turbo-Frame`; it does not invent validators or automatically apply
conditional request handling.

Explicit native Flask/Werkzeug response objects and directly assigned ETag header
strings remain application-owned. They are not rewritten; applications using
these escape hatches own representation-specific validators and conditional
ordering. A manual header override relinquishes framework tracking. Static asset
validators retain the asset delivery layer's behavior.

## Runtime ownership and verification

New applications receive the pinned upstream Turbo 8.0.23 runtime, license, and
provenance in application-owned assets. The existing asset pipeline handles both
development delivery and production fingerprinting. `turbo:install` preserves
local copies unless `--force` is explicit. It migrates the original generated CDN
URL without replacing surrounding script attributes; unfamiliar custom layouts
receive instructions rather than a second runtime. Existing view inheritance is
never rewritten automatically.

Public-API tests cover helper escaping, record/partial conventions, owner scopes,
format routing, negotiation, callback order, layout isolation, and conditional
validators. Generated-application browser workflows use the actual local runtime
with CSRF enabled and external requests blocked, exercising inline editing,
validation redisplay, lazy loading, top-level navigation, multi-operation Streams,
and HTML fallback. Production asset delivery is exercised separately.

Reference behavior: [turbo-rails frame helper](https://github.com/hotwired/turbo-rails/blob/main/app/helpers/turbo/frames_helper.rb),
[frame requests](https://github.com/hotwired/turbo-rails/blob/main/app/controllers/turbo/frames/frame_request.rb),
and [stream builder](https://github.com/hotwired/turbo-rails/blob/main/app/models/turbo/streams/tag_builder.rb).
