import re

from flaskteroids.fields import fields

field_types_pattern = rf"{'|'.join(k for k in fields.keys())}"
field_pattern = re.compile(rf"^([a-z_]+):({field_types_pattern})(!?)$")
association_pattern = re.compile(r"^([a-z_]+):(references|belongs_to)$")
attachment_pattern = re.compile(r"^([a-z_]+):(attachment|attachments)$")
rich_text_pattern = re.compile(r"^([a-z_]+):rich_text$")
