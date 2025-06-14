from importlib.resources import files, as_file
from mako.lookup import TemplateLookup


def template(root, *, path, params=None):
    with as_file(files(root)) as templates_dir:
        template_lookup = TemplateLookup(directories=[str(templates_dir)])
        params = params or {}
        template = template_lookup.get_template(path)
        return template.render(**params)
