# Mailers

Mailers inherit from `ActionMailer`. Each action sets template variables and calls `mail` with the recipient and subject.

```python
# app/mailers/user_mailer.py
from flaskteroids.mailer import ActionMailer

class UserMailer(ActionMailer):
    def welcome_email(self, user):
        self.user = user
        self.mail(to=user.email, subject="Welcome to My App!")
```

Call `deliver_now` to send the email immediately, or `deliver_later` to enqueue a background job:

```python
# Deliver now
UserMailer().welcome_email(user).deliver_now()

# Deliver later using a background job
UserMailer().welcome_email(user).deliver_later()
```
