import re
from flaskteroids.fields import fields


field_types_pattern = fr'{"|".join(k for k in fields.keys())}'
field_pattern = re.compile(fr'^([a-z_]+):({field_types_pattern})(!?)$')
association_pattern = re.compile(r'^([a-z_]+):(references|belongs_to)$')
