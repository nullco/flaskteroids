from app.mailers.${snake}_mailer import ${name}Mailer
from flaskteroids.mailer import MailerPreview


class ${name}MailerPreview(MailerPreview):
% for action in actions:
    def ${action}(self):
        return ${name}Mailer.with_params(greeting=self.params.get("greeting", "Hi")).${action}()

% endfor
% if not actions:
    pass
% endif
