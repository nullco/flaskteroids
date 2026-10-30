# ![Flaskteroids](assets/brand/logo-horizontal-light.svg#only-light) ![Flaskteroids](assets/brand/logo-horizontal-dark.svg#only-dark)

Flaskteroids is a Python MVC framework built on Flask, SQLAlchemy, and Celery.
It brings models, routes, templates, forms, background jobs, and email into a
shared application workflow.

These guides teach you how to build with Flaskteroids. Start with the tutorial
if you are new, or choose a component guide for the feature you are working on.

## Build your first application

[Getting started](getting_started.md) walks you through a product catalog.
You will create a model, display products, and build forms to add, edit, and
delete them. You need basic Python and HTML knowledge, but no experience with
the underlying libraries.

The rest of the store tutorial adds one feature at a time:

1. [Login and product images](tutorial/authentication_and_uploads.md) — protect
   catalog changes and upload a photo.
2. [Restock notifications](tutorial/restock_notifications.md) — connect
   subscriptions, inventory changes, background jobs, and email.
3. [Test the store](tutorial/testing.md) — check the workflows you have built.
4. [Prepare for deployment](tutorial/deployment.md) — review security and try
   the generated Docker setup.

Each part continues in the same application. You can stop after the first part
with a working catalog.

## Find a guide

Component guides explain a feature through focused examples. They assume you
have a generated application, but do not require completing the store tutorial.

### Models

- [Model basics](models/index.md) — create, query, validate, and save records.
- [Associations](models/associations.md) — connect models and work with related records.
- [Callbacks](models/callbacks.md) — run shared behavior during a record's lifecycle.
- [Fields](other/fields.md) — choose column types and understand submitted values.
- [Attribute encryption](models/encryption.md) — protect sensitive model data.

### Routing and controllers

- [Routing](controllers/routing.md) — connect URLs to actions.
- [Controller basics](controllers/index.md) — handle input and choose a response.
- [Rate limits](controllers/advanced.md) — limit repeated requests.
- [Building an API](controllers/api.md) — build and test a JSON API.

### Views and frontend

- [Templates and helpers](views/index.md) — render pages and share presentation logic.
- [Forms](other/forms.md) — accept input and help users correct mistakes.
- [Turbo Frames and Streams](views/turbo.md) — add inline navigation and page updates.
- [Assets](other/assets.md) — add styles and images, then build production files.
- [JavaScript with import maps](other/importmaps.md) — load modules without a build step.

### Background work and email

- [Background jobs](other/jobs.md) — move work outside a request.
- [Mailers](other/mailers.md) — compose, preview, test, and deliver email.

### Files and rich text

- [Attachments](other/attachments.md) — upload files and control download access.
- [Rich text](other/rich_text.md) — edit and display formatted content safely.

### Application setup and testing

- [Project structure](project_structure.md) — find where code and configuration belong.
- [Configuration](configuration.md) — choose settings and manage secrets.
- [Using the command line](other/cli.md) — generate components and run application tasks.
- [Middleware](other/middleware.md) — wrap requests before controller dispatch.
- [Internationalization](other/internationalization.md) — translate text and localize dates.
- [Testing](testing.md) — test models, requests, jobs, mail, and browser workflows.

Unless a guide says otherwise, run commands from your application root with
`bin/flask`. You do not need to activate the virtual environment.

To help improve these pages, see [Writing guides](contributing/guides.md).
