<% references = context.get("references", []) %>from app.models.application_model import ApplicationModel
% if references:
from flaskteroids.model import belongs_to
% endif
% if attachments:
from flaskteroids.model import has_one_attached, has_many_attached
% endif


class ${name}(ApplicationModel):
% for reference in references:
    belongs_to('${reference}')
% endfor
% for attachment in attachments:
    has_${attachment["cardinality"]}_attached('${attachment["name"]}')
% endfor
% if not attachments and not references:
    pass
% endif
