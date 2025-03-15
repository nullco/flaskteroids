import os
from jinja2 import Environment, FileSystemLoader

current_dir = os.path.dirname(os.path.abspath(__file__))
env = Environment(loader=FileSystemLoader(os.path.join(current_dir, 'templates')))


def build(template_name, template_params):
    template = env.get_template(template_name)
    return template.render(template_params)
