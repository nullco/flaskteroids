# Command-Line Interface (CLI)

Flaskteroids extends the `flask` CLI with a powerful set of tools to streamline development.

## Generators

Use the `flask generate` command to create various components:

*   **Authentication:**
    ```sh
    flask generate authentication
    ```
    Sets up a complete authentication system (routes, controllers, views).

*   **Controller:**
    ```sh
    flask generate controller <controller_name> [action1 action2 ...]
    ```
    *Example:* `flask generate controller users index show`

*   **Mailer:**
    ```sh
    flask generate mailer <mailer_name> [action1 action2 ...]
    ```
    *Example:* `flask generate mailer UserMailer welcome_email`

*   **Migration:**
    ```sh
    flask generate migration <migration_name>
    ```

*   **Model:**
    ```sh
    flask generate model <model_name> [field1:type ...]
    ```
    *Example:* `flask generate model User name:string email:string`

*   **Resource:**
    ```sh
    flask generate resource <resource_name> [field1:type ...]
    ```
    Generates a model and a RESTful controller.

*   **Scaffold:**
    ```sh
    flask generate scaffold <scaffold_name> [field1:type ...]
    ```
    Generates a model, RESTful controller, and views.
