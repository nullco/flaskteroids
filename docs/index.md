# ![Flaskteroids](assets/brand/logo-horizontal-light.svg#only-light) ![Flaskteroids](assets/brand/logo-horizontal-dark.svg#only-dark)

Flaskteroids is a Python MVC framework built on Flask, SQLAlchemy, and Celery. It uses Rails 8 as the reference for its conventions and framework behavior.

The framework chooses an application layout and discovers models, controllers, and templates in their conventional directories. It includes resource routing, database migrations, form helpers, background jobs, and email delivery. Flask APIs and extensions remain available when you need them.

Generators create models, controllers, scaffolds, mailers, and authentication code. Applications include environment-specific settings, encrypted credentials, and pytest-based tests with YAML fixtures and transactional rollback. Browser tests use Playwright.

Start with [Getting started](getting_started.md) to build a product catalog, learn the MVC workflow, and add authentication, uploads, email, and tests.

## Guides

- [Project structure](project_structure.md) and [configuration](configuration.md) explain where files live and how an application boots.
- The [models guide](models/index.md) covers associations, validations, callbacks, and queries.
- [Controllers](controllers/index.md) and [routing](controllers/routing.md) cover request handling and HTML or JSON responses.
- [Views](views/index.md) and [forms](other/forms.md) cover templates and form submissions.
- [Testing](testing.md) covers model, integration, job, mailer, and browser tests.
- The [CLI reference](other/cli.md) lists generators and credentials commands.
