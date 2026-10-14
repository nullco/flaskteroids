from app.models.application_model import ApplicationModel
% if attachments:
from flaskteroids.model import has_one_attached, has_many_attached
from flaskteroids.rules import rules
% endif


% if attachments:
@rules(
% for index, attachment in enumerate(attachments):
    has_${attachment["cardinality"]}_attached('${attachment["name"]}')${"," if index < len(attachments) - 1 else ""}
% endfor
)
% endif
class ${name}(ApplicationModel):
    pass
