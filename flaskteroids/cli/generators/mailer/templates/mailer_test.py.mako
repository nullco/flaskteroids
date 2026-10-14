from test.test_helper import MailerTest
from app.mailers.${snake}_mailer import ${name}Mailer


class ${name}MailerTest(MailerTest):
% for action in actions:
    def test_${action}(self):
        with self.assert_emails(1):
            ${name}Mailer().${action}().deliver_now()

% endfor
% if not actions:
    pass
% endif
