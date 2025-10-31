# Project Structure

A typical Flaskteroids project follows this structure:

```
my_project/
├── app/
│   ├── controllers/
│   ├── models/
│   ├── mailers/
│   ├── views/
│   └── jobs/
├── config/
│   └── routes.py
└── run.py
```

- `app/controllers`: Handle web requests and respond with data or rendered views.
- `app/models`: Define your application's data structure and database interactions.
- `app/views`: Contain the templates for your application's UI.
- `app/mailers`: Handle sending emails.
- `app/jobs`: Define background jobs to be run asynchronously.
- `config/routes.py`: Define the URL routes for your application.
