# ![Flaskteroids](assets/brand/logo-horizontal-light.svg#only-light) ![Flaskteroids](assets/brand/logo-horizontal-dark.svg#only-dark)

Flaskteroids is a Python MVC framework built on Flask, SQLAlchemy, and Celery.

Build web applications with a consistent project layout and tools that work
together: models, routes, templates, forms, background jobs, and email. Generators
create the starting code so you can focus on your application's behavior. Flask
APIs and extensions remain available when you need them.

Start with [Getting started](getting_started.md) to build a product catalog, learn the MVC workflow, and add authentication, uploads, email, and tests.

## Find a guide

| I want to… | Read |
| --- | --- |
| Find the right file or change settings | [Project structure](project_structure.md), [Configuration](configuration.md) |
| Store, query, or validate data | [Models](models/index.md), [Fields](other/fields.md) |
| Encrypt sensitive database values | [Attribute encryption](models/encryption.md) |
| Handle requests and define URLs | [Controllers](controllers/index.md), [Routing](controllers/routing.md) |
| Build pages and accept input | [Views](views/index.md), [Forms](other/forms.md) |
| Translate messages and format dates | [Internationalization](other/internationalization.md) |
| Add styles and images | [Assets](other/assets.md) |
| Upload files or add a text editor | [Attachments](other/attachments.md), [Rich text](other/rich_text.md) |
| Run work in the background or send email | [Jobs](other/jobs.md), [Mailers](other/mailers.md) |
| Check application behavior | [Testing](testing.md) |
| Look up a generator or command | [CLI reference](other/cli.md) |

Unless a guide says otherwise, run application commands from the application
root using `bin/flask`. You do not need to activate the virtual environment.
