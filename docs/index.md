# ![Flaskteroids](assets/brand/logo-horizontal-light.svg#only-light) ![Flaskteroids](assets/brand/logo-horizontal-dark.svg#only-dark)

Flaskteroids is a Python MVC framework built on Flask, SQLAlchemy, and Celery.

Build web applications with a consistent project layout and tools that work
together: models, routes, templates, forms, background jobs, and email. Generators
create the starting code so you can focus on your application's behavior. Flask
APIs and extensions remain available when you need them.

Start with [Getting started](getting_started.md) to build a product catalog, learn the MVC workflow, and add authentication, uploads, email, and tests.

## Find a guide

### Start here

- [Getting started](getting_started.md) — Build a product catalog while learning the framework's everyday workflows.
- [Project structure](project_structure.md) — Find where application code, configuration, migrations, and tests belong.

### Models

- [Model basics](models/index.md) — Create and query records, validate input, and work with associations, callbacks, and transactions.
- [Fields](other/fields.md) — Choose field types and modifiers for models and migrations.
- [Attribute encryption](models/encryption.md) — Encrypt sensitive model attributes.

### Routing and controllers

- [Routing](controllers/routing.md) — Connect URLs to actions and define resource routes.
- [Controller basics](controllers/index.md) — Handle request parameters, callbacks, rendering, and redirects.
- [Rate limits](controllers/advanced.md) — Limit requests and understand the cache boundaries.

### Views

- [Templates and helpers](views/index.md) — Render pages and share presentation logic through application helpers.
- [Forms](other/forms.md) — Build model-backed forms and filter submitted parameters.
- [Turbo Frames and Streams](views/turbo.md) — Add inline navigation and partial page updates.

### Other components

- [Mailers](other/mailers.md) — Compose and deliver email.
- [Rich text](other/rich_text.md) — Add an editor and render rich-text content safely.
- [Background jobs](other/jobs.md) — Enqueue work to run outside a request.
- [Attachments](other/attachments.md) — Upload and store files.

### Digging deeper

- [Testing](testing.md) — Test models, requests, jobs, mailers, and browser workflows.
- [Configuration](configuration.md) — Configure environments, databases, and encrypted credentials.
- [Command-line interface](other/cli.md) — Look up generators and application commands.
- [Assets](other/assets.md) — Serve source assets and build fingerprinted production files.
- [Import maps](other/importmaps.md) — Use native JavaScript modules and pin packages without Node.
- [Internationalization](other/internationalization.md) — Translate messages and localize dates and times.
- [Building an API](controllers/api.md) — Build a JSON API without browser defaults.

Unless a guide says otherwise, run application commands from the application
root using `bin/flask`. You do not need to activate the virtual environment.
