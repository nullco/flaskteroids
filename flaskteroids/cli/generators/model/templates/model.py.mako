<% references = context.get("references", []) %>from app.models.application_model import ApplicationModel
% if references:
from flaskteroids.model import belongs_to
% endif
% if attachments:
from flaskteroids.model import has_one_attached, has_many_attached
% endif
% if attachments or references:
from flaskteroids.rules import rules
% endif


% if attachments or references:
@rules(
% for reference in references:
    belongs_to('${reference}'),
% endfor
% for attachment in attachments:
    has_${attachment["cardinality"]}_attached('${attachment["name"]}'),
% endfor
)
% endif
class ${name}(ApplicationModel):
    pass
