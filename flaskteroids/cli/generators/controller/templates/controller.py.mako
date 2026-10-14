from app.controllers.application_controller import ApplicationController


class ${name}Controller(ApplicationController):
% for action in actions:
    def ${action}(self):
        pass

% endfor
% if not actions:
    pass
% endif
