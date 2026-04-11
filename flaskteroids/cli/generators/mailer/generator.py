import click
from flaskteroids.cli.artifacts import ArtifactsBuilder
from flaskteroids.cli.generators.mailer import cmd_parser


def generate(mailer, actions):
    params = cmd_parser.parse(mailer, [])['parsed']
    snake = params['snake']
    camel = params['camel']
    ab = ArtifactsBuilder('.', click.echo)
    ab.file(f'app/mailers/{snake}_mailer.py', _mailer(name=camel, actions=actions))
    ab.dir(f'app/views/{snake}_mailer/')
    for action in actions:
        html_file_name = f'app/views/{snake}_mailer/{action}.html'
        txt_file_name = f'app/views/{snake}_mailer/{action}.txt'
        ab.file(html_file_name, _html_view(name=camel, action=action, file_name=html_file_name))
        ab.file(txt_file_name, _txt_view(name=camel, action=action, file_name=txt_file_name))


def _mailer(*, name, actions):
    action_fns = []
    for action in actions:
        action_fns.append(f"""
    def {action}(self):
        self.greeting = 'Hi'
        self.mail(to='to@example.org')
        """)
    action_fns = ''.join(action_fns) or 'pass'
    return f"""
from app.mailers.application_mailer import ApplicationMailer


class {name}Mailer(ApplicationMailer):
    {action_fns}"""

def _html_view(name, action, file_name):
    return f"""
<h1>{name}#{action}</h1>
<p>
     {{{{ greeting }}}}, find me in {file_name}
</p>
    """


def _txt_view(name, action, file_name):
    return f"""
{name}#{action}

{{{{ greeting }}}}, find me in {file_name}
    """
