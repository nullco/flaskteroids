import click
from flaskteroids.cli.artifacts import ArtifactsBuilder
from flaskteroids.cli.generators.mailer import cmd_parser
from flaskteroids.inflector import inflector


def generate(mailer, actions):
    params = cmd_parser.parse(mailer, [])['parsed']
    snake = params['snake']
    camel = params['camel']
    ab = ArtifactsBuilder('.', click.echo)
    ab.file(f'app/mailers/{snake}_mailer.py', _mailer(name=camel, actions=actions))
    ab.dir(f'app/views/{snake}_mailer/')
    ab.file(
        f'test/mailers/{snake}_mailer_test.py',
        _mailer_test(name=camel, actions=actions),
    )
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
        return self.mail(to='to@example.org', subject='{action.title()}')
        """)
    action_fns = ''.join(action_fns) or 'pass'
    return f"""
from app.mailers.application_mailer import ApplicationMailer


class {name}Mailer(ApplicationMailer):
    {action_fns}"""

def _mailer_test(*, name, actions):
    tests = []
    for action in actions:
        tests.append(f'''    def test_{action}(self):
        with self.assert_emails(1):
            {name}Mailer().{action}().deliver_now()
''')
    body = "\n".join(tests) or "    pass\n"
    return f"""
from test.test_helper import MailerTest
from app.mailers.{inflector.underscore(name)}_mailer import {name}Mailer


class {name}MailerTest(MailerTest):
{body}
    """


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
