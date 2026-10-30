# Prepare the store for deployment

A working development application is a starting point for deployment, not a
production configuration. This final part of the store tutorial explains what to
review before you publish the application.

After working through this guide, you will know how to:

- Run the store's tests in continuous integration.
- Review the security boundaries used throughout the tutorial.
- Check the generated Docker setup and identify the services production needs.

Continue with the `store` application from [Test the store](testing.md).
The Docker example requires Docker; a real deployment also requires a hosting
platform and its own service and secret configuration.

## Security and continuous integration

Before deploying, run the complete suite:

```sh
bin/flask test
bin/flask test:system
```

The generated `.github/workflows/test.yml` provides a starting CI workflow.
Review it and keep your application's tests and browser dependencies up to date.
Linting or security scanners you choose for your application need their own
configuration.

Keep these boundaries in mind:

- Use `self.params.expect()` allowlists, even when the browser form looks harmless.
- Protect write actions on the server, not just their links in templates.
- Keep CSRF protection enabled; form helpers include the required tokens.
- Let Jinja and helpers escape user input. Never mark product descriptions safe
  merely to display formatting.
- Keep master keys, passwords, database URLs, and SMTP credentials out of Git.
- Do not expose the debug server to production traffic.
- Configure HTTPS, upload limits, access policies, and backups for your deployment.

## Prepare for production

Flaskteroids generates a Dockerfile and deployment scripts. Start by reading
your app's `deploy/README.md`, which contains the commands matching your generated
application. You will need to choose and configure your own hosting platform.

For a local production-mode Docker check, commit your application lockfile and
build an image:

```sh
docker build -t store .
docker volume create store-storage
```

Supply `FLASKTEROIDS_MASTER_KEY` at runtime using your secret manager. For a local
check only, read the generated key into your shell and forward it to Docker:

```sh
export FLASKTEROIDS_MASTER_KEY="$(tr -d '\n' < config/master.key)"
docker run --rm -p 8000:8000 \
  --env FLASKTEROIDS_MASTER_KEY \
  --volume store-storage:/app/storage \
  store
```

Open <http://127.0.0.1:8000>. This is a **separate production database**, so it will
not contain the development products or account you created earlier. Stop the
container with `Ctrl-C` when finished and unset the key:

```sh
unset FLASKTEROIDS_MASTER_KEY
```

The default web startup prepares the production database before launching
Gunicorn. The volume keeps SQLite data and local uploads across container
restarts. The image runs unprivileged; host bind mounts must be writable by its
application user.

For a real deployment:

1. Provide the matching credentials key and environment settings through your
   hosting platform's secret management.
2. Configure your database and install its driver if using PostgreSQL or MySQL.
3. Coordinate migrations once per release when running multiple instances; do
   not use each web instance as migration coordination.
4. Configure SMTP and a sender address for real mail, your canonical host via
   `SERVER_NAME` for email links, external storage if needed, and a Celery broker
   and worker. The tutorial's console adapter is only enabled in development.
5. Put the application behind HTTPS and arrange persistent storage and backups.
6. Create an initial user through an application shell in the production
   environment, using your host's execution facility and the account creation
   code from [the login guide](authentication_and_uploads.md#require-login-to-change-products).
   Do not add credentials to the image or Git.

See [Configuration](../configuration.md#preparing-for-deployment) and your generated
deployment guide for release commands and service settings. The Docker check
above is not a complete internet-facing deployment recipe.

## Where to go next

You started with an empty application and built a working store: visitors browse
products, owners manage stock and images, and subscribers hear when a product
returns. Tests now check the behavior that makes those features work together.

Next, try expanding it:

- Add product categories with another model and association.
- Add pagination and filtering to the catalog.
- Confirm subscription addresses before enabling notifications for real visitors.
- Write a browser test for the complete subscribe-and-unsubscribe journey.
- Return JSON alongside HTML using controller content negotiation.

Explore the focused guides as you go:

- [Models](../models/index.md): queries, transactions, associations, and callbacks.
- [Controllers](../controllers/index.md) and [Routing](../controllers/routing.md).
- [Views](../views/index.md) and [Forms](../other/forms.md).
- [Attachments](../other/attachments.md), [Mailers](../other/mailers.md), and
  [Background jobs](../other/jobs.md).
- [Testing](../testing.md), [Configuration](../configuration.md), and
  [CLI](../other/cli.md).
