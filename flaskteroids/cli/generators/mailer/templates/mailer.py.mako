from app.mailers.application_mailer import ApplicationMailer
from flaskteroids import params


class ${name}Mailer(ApplicationMailer):
% for action in actions:
    def ${action}(self):
        self.greeting = params.get('greeting', 'Hi')
        return self.mail(to='to@example.org', subject='${action.title()}')

% endfor
% if not actions:
    pass
% endif
