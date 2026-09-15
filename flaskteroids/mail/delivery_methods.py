import smtplib


class SMTPDeliveryMethod:
    def __init__(self, application, config):
        self.config = config

    def deliver(self, message):
        smtp = self.config.smtp_settings
        with smtplib.SMTP(smtp.host, smtp.port) as server:
            server.starttls()
            server.login(smtp.username, smtp.password)
            server.send_message(message)
