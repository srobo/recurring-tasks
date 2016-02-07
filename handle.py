from pathlib import Path
import argparse
import yaml
from collections import namedtuple
from termcolor import cprint
import textwrap
import urllib.parse
from getpass import getpass

ROOT = Path(__file__).parent

parser = argparse.ArgumentParser()
parser.add_argument('base', help='Root ticket to generate')
parser.add_argument('year', help='SR year to generate for')
parser.add_argument('-t', '--trac-root',
                    help='Base URL for the Trac installation',
                    default=None)
arguments = parser.parse_args()
BASE = arguments.base
YEAR = arguments.year

CYCLE = object()
elements = {}

Ticket = namedtuple('Ticket',
                    ['summary', 'priority', 'component',
                     'original_name',
                     'milestone', 'description', 'dependencies'])

def trac_description_text(ticket):
    text = textwrap.fill(ticket.description, width=72)
    text += '\n\nOriginal: [recurring-task:{}]'.format(ticket.original_name)
    if ticket.dependencies:
        text += '\n\nDependencies:\n\n'
        for dep in sorted(ticket.dependencies):
            text += (' * #{} {}'.format(dep, TRAC.title(dep)).rstrip()) + '\n'
    return text.strip()

class FakeTrac(object):
    def __init__(self):
        self.next_ticket = 2673
        self._known_titles = {}

    def submit(self, ticket):
        ticket_number = self.next_ticket
        self.next_ticket += 1
        PRIORITY_COLOURS = {'trivial': 'cyan',
                            'minor': 'blue',
                            'major': 'green',
                            'critical': 'yellow',
                            'blocker': 'red'}
        cprint('#{}: {}'.format(ticket_number, ticket.summary),
               PRIORITY_COLOURS[ticket.priority],
               attrs=['bold'])
        desc = trac_description_text(ticket)
        cprint(textwrap.indent(desc, '  '))
        self._known_titles[ticket_number] = ticket.summary
        return ticket_number

    def title(self, ticket_number):
        return self._known_titles.get(ticket_number, '')

class RealTrac(object):
    def __init__(self, root):
        self.root = root
        import xmlrpc.client as xml
        attrs = urllib.parse.urlsplit(root)
        username = input('SR username: ')
        password = getpass('SR password: ')
        generated_netloc = '{}:{}@{}{}'.format(urllib.parse.quote(username),
                                               urllib.parse.quote(password),
                                               attrs.hostname,
                                               ':{}'.format(attrs.port)
                                                 if attrs.port is not None
                                                 else '')
        generated_parts = (attrs.scheme,
                           generated_netloc,
                           attrs.path.rstrip('/') + '/login/xmlrpc',
                           '', '')
        target_url = urllib.parse.urlunsplit(generated_parts)
        self._xml = xml.ServerProxy(target_url)
        print(self._xml.system.methodHelp('ticket.create'))

    def submit(self, ticket):
        desc = trac_description_text(ticket)
        attrs = {}
        if ticket.component is not None:
            attrs['component'] = ticket.component
        if ticket.milestone is not None:
            attrs['milestone'] = ticket.milestone
        attrs['priority'] = ticket.priority
        ticket_number = self._xml.ticket.create(ticket.summary,
                                                desc,
                                                attrs,
                                                False)
        print('Created ticket #{}: {}'.format(ticket_number,
                                              ticket.summary))
        return ticket_number

    def title(self, ticket_number):
        ticket_data = self._xml.ticket.get(ticket_number)
        return ticket_data[3]['summary']

if arguments.trac_root is not None:
    TRAC = RealTrac(arguments.trac_root)
else:
    TRAC = FakeTrac()

def add(element):
    if element in elements:
        previous = elements[element]
        if previous is CYCLE:
            raise RuntimeError('cyclic dependency on {}'.format(element))
        return previous
    else:
        elements[element] = CYCLE
        generated = process(element)
        ticket_id = TRAC.submit(generated)
        elements[element] = ticket_id
        return ticket_id

def handle_dep(key):
    if isinstance(key, int):
        return key
    return add(key)

COMPONENTS = ('Arena', 'Competition', 'Website', 'sysadmin',
              'Media', 'Rules', 'SRComp suite', 'Tall Ship')

def process(element_name):
    path = (ROOT / element_name).with_suffix('.yaml')

    with path.open('r') as f:
        data = f.read()
    data = data.replace('$YYYY', str(YEAR))
    data = data.replace('$SRYYYY', 'SR{}'.format(YEAR))
    raw_elements = yaml.load(data)
    if 'summary' not in raw_elements and 'description' not in raw_elements:
        raise RuntimeError('{} contains neither a summary nor a description'.format(path))
    description = raw_elements.get('description', '')

    if not len(description.splitlines()) == 0:
        summary = raw_elements.get('summary', description.splitlines()[0])
    else:
        summary = raw_elements["summary"]

    component = raw_elements.get('component')
    priority = raw_elements.get('priority', 'major')
    if priority not in ('trivial', 'minor', 'major', 'critical', 'blocker'):
        raise RuntimeError('{} has an invalid priority: {}'.format(path, priority))
    if component not in COMPONENTS:
        raise RuntimeError('{} has an unknown component: {}'.format(path, component))
    milestone = raw_elements.get('milestone')
    dependencies = raw_elements.get('dependencies', ())
    computed_dependencies = [handle_dep(element) for element in dependencies]
    data = Ticket(summary=summary,
                  component=component,
                  priority=priority,
                  milestone=milestone,
                  original_name=element_name,
                  description=description,
                  dependencies=computed_dependencies)
    return data

add(BASE)

