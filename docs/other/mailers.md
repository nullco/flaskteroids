### Mailers

Mailers inherit from `ActionMailer` and are used to send emails from your application. They work similarly to controllers, with actions that correspond to email templates.

```python
# app/mailers/user_mailer.py
from flaskteroids.mailer import ActionMailer

class UserMailer(ActionMailer):
    def welcome_email(self, user):
        self.user = user
        self.mail(to=user.email, subject="Welcome to My App!")
```

You can then deliver the email synchronously or asynchronously:

```python
# Deliver now
UserMailer().welcome_email(user).deliver_now()

# Deliver later using a background job
UserMailer().welcome_email(user).deliver_later()
```
